import uuid
from datetime import datetime, timedelta, timezone

from telemetry_aggregates.backfill import run_backfill_once
from telemetry_aggregates.models import HourlyAggregate
from telemetry_aggregates.telemetry_read_models import store_product_thresholds, temperature_readings

HOUR = datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc)


async def _seed_telemetry_db(telemetry_session_factory, store_id, product_id, temperatures, hour=HOUR):
    async with telemetry_session_factory() as session:
        await session.execute(
            store_product_thresholds.insert().values(store_id=store_id, product_id=product_id)
        )
        for i, temp in enumerate(temperatures):
            await session.execute(
                temperature_readings.insert().values(
                    store_id=store_id, temperature=temp, recorded_at=hour + timedelta(minutes=i * 5)
                )
            )
        await session.commit()


async def test_backfill_computes_true_aggregate_from_raw_data(session_factory, telemetry_session_factory):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    await _seed_telemetry_db(telemetry_session_factory, store_id, product_id, [4.0, 6.0, 5.0, 9.0])

    written = await run_backfill_once(session_factory, telemetry_session_factory, now=HOUR + timedelta(minutes=50))

    assert written == 1
    async with session_factory() as session:
        row = await session.get(HourlyAggregate, (store_id, product_id, HOUR))

    assert float(row.avg_temperature) == 6.0
    assert float(row.min_temperature) == 4.0
    assert float(row.max_temperature) == 9.0
    assert row.reading_count == 4


async def test_backfill_overwrites_a_drifted_row(session_factory, telemetry_session_factory):
    """Simulates the incremental path having missed events (consumer
    downtime): the existing row reflects only 1 of the 4 real readings.
    Backfill must overwrite it to match the true computed values, not
    merge."""
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    await _seed_telemetry_db(telemetry_session_factory, store_id, product_id, [4.0, 6.0, 5.0, 9.0])

    async with session_factory() as session:
        session.add(
            HourlyAggregate(
                store_id=store_id,
                product_id=product_id,
                hour_bucket=HOUR,
                avg_temperature=4.0,
                min_temperature=4.0,
                max_temperature=4.0,
                reading_count=1,
            )
        )
        await session.commit()

    await run_backfill_once(session_factory, telemetry_session_factory, now=HOUR + timedelta(minutes=50))

    async with session_factory() as session:
        row = await session.get(HourlyAggregate, (store_id, product_id, HOUR))

    assert float(row.avg_temperature) == 6.0
    assert row.reading_count == 4  # not 1 (missed events) and not 5 (merged)


async def test_backfill_covers_current_and_previous_hour(session_factory, telemetry_session_factory):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    previous_hour = HOUR
    current_hour = HOUR + timedelta(hours=1)
    await _seed_telemetry_db(telemetry_session_factory, store_id, product_id, [5.0], hour=previous_hour)
    async with telemetry_session_factory() as session:
        await session.execute(
            temperature_readings.insert().values(store_id=store_id, temperature=10.0, recorded_at=current_hour + timedelta(minutes=1))
        )
        await session.commit()

    written = await run_backfill_once(session_factory, telemetry_session_factory, now=current_hour + timedelta(minutes=5))

    assert written == 2
    async with session_factory() as session:
        previous_row = await session.get(HourlyAggregate, (store_id, product_id, previous_hour))
        current_row = await session.get(HourlyAggregate, (store_id, product_id, current_hour))

    assert float(previous_row.avg_temperature) == 5.0
    assert float(current_row.avg_temperature) == 10.0


async def test_backfill_is_idempotent_across_repeated_runs(session_factory, telemetry_session_factory):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    await _seed_telemetry_db(telemetry_session_factory, store_id, product_id, [4.0, 6.0, 5.0, 9.0])

    await run_backfill_once(session_factory, telemetry_session_factory, now=HOUR + timedelta(minutes=50))
    await run_backfill_once(session_factory, telemetry_session_factory, now=HOUR + timedelta(minutes=55))
    await run_backfill_once(session_factory, telemetry_session_factory, now=HOUR + timedelta(minutes=59))

    async with session_factory() as session:
        row = await session.get(HourlyAggregate, (store_id, product_id, HOUR))

    assert float(row.avg_temperature) == 6.0
    assert row.reading_count == 4  # unchanged by repeated runs — pure recompute, not accumulation
