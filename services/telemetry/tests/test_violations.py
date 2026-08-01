import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from telemetry.models import Incident, OutboxEvent, Store, StoreProductThreshold, TemperatureReading
from telemetry.violations import check_violations

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def session(client) -> AsyncSession:
    async with client.app.state.session_factory() as session:
        yield session


async def _seed(
    session: AsyncSession,
    max_temp: float,
    readings: list[tuple[float, datetime]],
) -> tuple[uuid.UUID, uuid.UUID]:
    store_id = uuid.uuid4()
    product_id = uuid.uuid4()
    session.add(Store(id=store_id, name=str(store_id)))
    session.add(StoreProductThreshold(store_id=store_id, product_id=product_id, max_temp=max_temp))
    for temperature, recorded_at in readings:
        session.add(TemperatureReading(store_id=store_id, temperature=temperature, recorded_at=recorded_at))
    await session.flush()
    return store_id, product_id


async def test_no_violation_when_less_than_one_hour_of_coverage(session):
    # All readings are within the last hour, but none anchor the window at
    # or before window_start (NOW - 1h) — not enough historical coverage.
    readings = [(10.0, NOW - timedelta(minutes=30)), (10.0, NOW - timedelta(minutes=5))]
    await _seed(session, max_temp=5.0, readings=readings)

    created = await check_violations(session, now=NOW)

    assert created == 0
    assert (await session.execute(select(Incident))).scalars().all() == []


async def test_violation_when_full_hour_all_readings_over(session):
    readings = [
        (10.0, NOW - timedelta(hours=1)),
        (10.0, NOW - timedelta(minutes=30)),
        (10.0, NOW),
    ]
    await _seed(session, max_temp=5.0, readings=readings)

    created = await check_violations(session, now=NOW)

    assert created == 1
    incidents = (await session.execute(select(Incident))).scalars().all()
    assert len(incidents) == 1
    assert incidents[0].temperature_at_outbreak == 10.0
    assert incidents[0].deviation == 5.0

    outbox = (await session.execute(select(OutboxEvent))).scalars().all()
    assert len(outbox) == 1
    assert outbox[0].event_type == "TemperatureThresholdViolated"
    assert outbox[0].payload["stock_id"]


async def test_no_violation_when_exactly_one_degree_over(session):
    # max_temp=5, readings at exactly 6.0 -> 6.0 > 5+1 is False (strict >).
    readings = [
        (6.0, NOW - timedelta(hours=1)),
        (6.0, NOW),
    ]
    await _seed(session, max_temp=5.0, readings=readings)

    created = await check_violations(session, now=NOW)

    assert created == 0
    assert (await session.execute(select(Incident))).scalars().all() == []


async def test_no_violation_when_average_over_but_one_reading_within_margin(session):
    # Average (10 + 6) / 2 = 8, well over max_temp+1=6, but the second
    # reading (6.0) does not itself exceed the margin -> not sustained.
    readings = [
        (10.0, NOW - timedelta(hours=1)),
        (6.0, NOW),
    ]
    await _seed(session, max_temp=5.0, readings=readings)

    created = await check_violations(session, now=NOW)

    assert created == 0
    assert (await session.execute(select(Incident))).scalars().all() == []


async def test_no_duplicate_incident_within_same_open_window(session):
    readings = [
        (10.0, NOW - timedelta(hours=1)),
        (10.0, NOW),
    ]
    store_id, product_id = await _seed(session, max_temp=5.0, readings=readings)
    session.add(
        Incident(
            store_id=store_id,
            product_id=product_id,
            started_at=NOW - timedelta(minutes=10),
            temperature_at_outbreak=10.0,
            deviation=5.0,
        )
    )
    await session.flush()

    created = await check_violations(session, now=NOW)

    assert created == 0
    incidents = (await session.execute(select(Incident))).scalars().all()
    assert len(incidents) == 1  # still just the pre-existing one


async def test_no_violation_when_threshold_not_set(session):
    store_id = uuid.uuid4()
    product_id = uuid.uuid4()
    session.add(Store(id=store_id, name=str(store_id)))
    session.add(StoreProductThreshold(store_id=store_id, product_id=product_id, max_temp=None))
    session.add(TemperatureReading(store_id=store_id, temperature=99.0, recorded_at=NOW - timedelta(hours=1)))
    await session.flush()

    created = await check_violations(session, now=NOW)

    assert created == 0
