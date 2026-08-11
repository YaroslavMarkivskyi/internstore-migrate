"""The core correctness claim of the hybrid design: whichever of the two
update paths runs, and in whichever order, the aggregate for a given
`{store, product, hour}` converges to the same ground-truth value once
backfill has had a chance to run — because backfill is a *pure overwrite*
computed directly from telemetry-db's raw readings, never a merge, so it
doesn't matter what the incremental path already wrote (correct, partial,
or even double-counted from a consumer restart) before backfill runs.

This intentionally does NOT claim that interleaving an incremental event
with a backfill overwrite for the *same underlying reading* mid-flight is
consistent at every instant — see the README's "Idempotency guarantee"
section for why that's not the claim, and what actually bounds the drift
(one backfill interval).
"""

import uuid
from datetime import datetime, timedelta, timezone

from telemetry_aggregates.backfill import run_backfill_once
from telemetry_aggregates.consumers.telemetry_events import handle_temperature_recorded
from telemetry_aggregates.models import HourlyAggregate
from telemetry_aggregates.telemetry_read_models import store_product_thresholds, temperature_readings

HOUR = datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc)
TEMPERATURES = [4.0, 6.0, 5.0, 9.0]  # true avg 6.0, min 4.0, max 9.0, count 4


async def _seed_raw_readings(telemetry_session_factory, store_id, product_id, temperatures):
    """Models the real system's invariant: a raw temperature_readings row
    always exists before its corresponding TemperatureRecorded event is
    published (outbox pattern — insert, then stage the event, in the same
    transaction). So by the time any event reaches this service's
    consumer, telemetry-db's raw table already reflects that reading,
    independent of Kafka."""
    async with telemetry_session_factory() as session:
        await session.execute(
            store_product_thresholds.insert().values(
                store_id=store_id, product_id=product_id, tracked_since=HOUR - timedelta(days=1)
            )
        )
        for i, temp in enumerate(temperatures):
            await session.execute(
                temperature_readings.insert().values(
                    store_id=store_id, temperature=temp, recorded_at=HOUR + timedelta(minutes=i * 5)
                )
            )
        await session.commit()


async def _consume_all_events(session_factory, store_id, product_id, temperatures):
    async with session_factory() as session:
        for i, temp in enumerate(temperatures):
            payload = {
                "store_id": str(store_id),
                "product_id": str(product_id),
                "temperature": temp,
                "humidity": None,
                "recorded_at": (HOUR + timedelta(minutes=i * 5)).isoformat(),
            }
            await handle_temperature_recorded(session, uuid.uuid4(), payload)
        await session.commit()


async def _get_row(session_factory, store_id, product_id):
    async with session_factory() as session:
        return await session.get(HourlyAggregate, (store_id, product_id, HOUR))


async def test_consumer_then_backfill_converges_to_truth(session_factory, telemetry_session_factory):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    await _seed_raw_readings(telemetry_session_factory, store_id, product_id, TEMPERATURES)

    await _consume_all_events(session_factory, store_id, product_id, TEMPERATURES)
    await run_backfill_once(session_factory, telemetry_session_factory, now=HOUR + timedelta(minutes=50))

    row = await _get_row(session_factory, store_id, product_id)
    assert (float(row.avg_temperature), float(row.min_temperature), float(row.max_temperature), row.reading_count) == (
        6.0,
        4.0,
        9.0,
        4,
    )


async def test_backfill_only_converges_to_the_same_truth(session_factory, telemetry_session_factory):
    """The other order: backfill runs against the raw data with no
    incremental events ever consumed (e.g. the consumer was never up for
    this window). Same final values as the consumer-then-backfill order
    above — backfill's output depends only on raw data, not on what the
    incremental path did or didn't do first."""
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    await _seed_raw_readings(telemetry_session_factory, store_id, product_id, TEMPERATURES)

    await run_backfill_once(session_factory, telemetry_session_factory, now=HOUR + timedelta(minutes=50))

    row = await _get_row(session_factory, store_id, product_id)
    assert (float(row.avg_temperature), float(row.min_temperature), float(row.max_temperature), row.reading_count) == (
        6.0,
        4.0,
        9.0,
        4,
    )


async def test_backfill_converges_to_truth_regardless_of_incremental_drift(session_factory, telemetry_session_factory):
    """Whatever state the incremental path left the row in — correct,
    partial (missed events), or over-counted (e.g. a consumer that
    reprocessed events already covered by an earlier backfill) — the next
    backfill cycle overwrites it back to the same ground truth. This is
    the actual mechanism that stops permanent double-counting: not
    perfect real-time consistency between the two paths, but a bounded
    (one backfill interval) self-heal, driven by backfill always being a
    pure function of raw data rather than a merge."""
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    await _seed_raw_readings(telemetry_session_factory, store_id, product_id, TEMPERATURES)

    async with session_factory() as session:
        session.add(
            HourlyAggregate(
                store_id=store_id,
                product_id=product_id,
                hour_bucket=HOUR,
                avg_temperature=999.0,  # arbitrarily wrong / drifted
                min_temperature=-50.0,
                max_temperature=999.0,
                reading_count=42,
            )
        )
        await session.commit()

    await run_backfill_once(session_factory, telemetry_session_factory, now=HOUR + timedelta(minutes=50))

    row = await _get_row(session_factory, store_id, product_id)
    assert (float(row.avg_temperature), float(row.min_temperature), float(row.max_temperature), row.reading_count) == (
        6.0,
        4.0,
        9.0,
        4,
    )


async def test_repeated_backfill_runs_are_a_noop_once_converged(session_factory, telemetry_session_factory):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    await _seed_raw_readings(telemetry_session_factory, store_id, product_id, TEMPERATURES)

    await run_backfill_once(session_factory, telemetry_session_factory, now=HOUR + timedelta(minutes=50))
    first = await _get_row(session_factory, store_id, product_id)
    first_values = (float(first.avg_temperature), float(first.min_temperature), float(first.max_temperature), first.reading_count)

    await run_backfill_once(session_factory, telemetry_session_factory, now=HOUR + timedelta(minutes=55))
    second = await _get_row(session_factory, store_id, product_id)
    second_values = (
        float(second.avg_temperature),
        float(second.min_temperature),
        float(second.max_temperature),
        second.reading_count,
    )

    assert first_values == second_values
