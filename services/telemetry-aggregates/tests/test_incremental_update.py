import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from telemetry_aggregates.consumers.telemetry_events import handle_temperature_recorded
from telemetry_aggregates.models import HourlyAggregate, ProcessedEvent


def _payload(store_id: uuid.UUID, product_id: uuid.UUID, temperature: float, recorded_at: datetime) -> dict:
    return {
        "store_id": str(store_id),
        "product_id": str(product_id),
        "temperature": temperature,
        "humidity": 40,
        "recorded_at": recorded_at.isoformat(),
    }


async def test_first_event_for_a_bucket_creates_a_row(session_factory):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    recorded_at = datetime(2026, 8, 11, 14, 5, tzinfo=timezone.utc)

    async with session_factory() as session:
        await handle_temperature_recorded(session, uuid.uuid4(), _payload(store_id, product_id, 5.0, recorded_at))
        await session.commit()

    async with session_factory() as session:
        row = await session.get(HourlyAggregate, (store_id, product_id, datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc)))

    assert row is not None
    assert float(row.avg_temperature) == 5.0
    assert float(row.min_temperature) == 5.0
    assert float(row.max_temperature) == 5.0
    assert row.reading_count == 1


async def test_running_average_is_correct_across_a_sequence(session_factory):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    base = datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc)
    temperatures = [4.0, 6.0, 5.0, 9.0]  # avg 6.0, min 4.0, max 9.0, count 4

    async with session_factory() as session:
        for i, temp in enumerate(temperatures):
            await handle_temperature_recorded(
                session, uuid.uuid4(), _payload(store_id, product_id, temp, base + timedelta(minutes=i * 5))
            )
        await session.commit()

    async with session_factory() as session:
        row = await session.get(HourlyAggregate, (store_id, product_id, base))

    assert float(row.avg_temperature) == 6.0
    assert float(row.min_temperature) == 4.0
    assert float(row.max_temperature) == 9.0
    assert row.reading_count == 4


async def test_new_hour_creates_a_new_row_rather_than_merging(session_factory):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    hour_one = datetime(2026, 8, 11, 14, 30, tzinfo=timezone.utc)
    hour_two = datetime(2026, 8, 11, 15, 5, tzinfo=timezone.utc)

    async with session_factory() as session:
        await handle_temperature_recorded(session, uuid.uuid4(), _payload(store_id, product_id, 5.0, hour_one))
        await handle_temperature_recorded(session, uuid.uuid4(), _payload(store_id, product_id, 20.0, hour_two))
        await session.commit()

    async with session_factory() as session:
        rows = list((await session.execute(select(HourlyAggregate).order_by(HourlyAggregate.hour_bucket))).scalars())

    assert len(rows) == 2
    assert float(rows[0].avg_temperature) == 5.0
    assert rows[0].reading_count == 1
    assert float(rows[1].avg_temperature) == 20.0
    assert rows[1].reading_count == 1


async def test_redelivery_of_the_same_event_is_a_noop(session_factory):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    recorded_at = datetime(2026, 8, 11, 14, 5, tzinfo=timezone.utc)
    event_id = uuid.uuid4()
    payload = _payload(store_id, product_id, 5.0, recorded_at)

    async with session_factory() as session:
        await handle_temperature_recorded(session, event_id, payload)
        await session.commit()
        await handle_temperature_recorded(session, event_id, payload)  # redelivery
        await session.commit()

    async with session_factory() as session:
        row = await session.get(HourlyAggregate, (store_id, product_id, datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc)))
        processed = list((await session.execute(select(ProcessedEvent))).scalars())

    assert row.reading_count == 1  # not 2
    assert len(processed) == 1
