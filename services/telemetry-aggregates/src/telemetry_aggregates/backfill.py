import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from telemetry_aggregates.aggregation import full_stats, truncate_to_hour
from telemetry_aggregates.models import HourlyAggregate
from telemetry_aggregates.telemetry_read_models import store_product_thresholds, temperature_readings

logger = logging.getLogger(__name__)


async def run_backfill_once(
    aggregates_session_factory: async_sessionmaker,
    telemetry_session_factory: async_sessionmaker,
    now: datetime | None = None,
) -> int:
    """The correctness backstop: for the current and previous hour (the
    previous hour catches readings that arrived right at/after an hour
    boundary before this cycle ran), recompute avg/min/max/count directly
    from telemetry-db's raw `temperature_readings` and **overwrite** (not
    merge) the corresponding `hourly_aggregates` row. Self-heals whatever
    the incremental consumer missed or double-applied since the last cycle
    — see README's "Idempotency guarantee" section.

    Telemetry's raw readings carry only `store_id` (no `product_id` — see
    telemetry/routers/measurements.py); a store's readings apply to every
    product it currently tracks (`store_product_thresholds`), mirroring
    exactly how telemetry fans out one `TemperatureRecorded` event per
    tracked product for a single physical reading — **as of the time each
    reading was recorded**, not the current snapshot. A reading from before
    a product was ever added to the store is excluded from that product's
    aggregate (via `store_product_thresholds.tracked_since`), same as the
    incremental consumer never received a `TemperatureRecorded` event for
    that pairing in the first place — see STR-148's live-verification
    finding in the README for why this matters (backfill used to
    retroactively fold pre-association readings into a newly-tracked
    product's aggregate). Returns the number of `{store, product, hour}`
    rows written.
    """
    now = now or datetime.now(timezone.utc)
    current_bucket = truncate_to_hour(now)
    previous_bucket = current_bucket - timedelta(hours=1)
    buckets = [previous_bucket, current_bucket]

    written = 0
    async with telemetry_session_factory() as telemetry_session:
        threshold_rows = (
            await telemetry_session.execute(
                select(
                    store_product_thresholds.c.store_id,
                    store_product_thresholds.c.product_id,
                    store_product_thresholds.c.tracked_since,
                )
            )
        ).all()
        products_by_store: dict = defaultdict(list)
        for store_id, product_id, tracked_since in threshold_rows:
            products_by_store[store_id].append((product_id, tracked_since))

        for bucket in buckets:
            window_end = bucket + timedelta(hours=1)
            reading_rows = (
                await telemetry_session.execute(
                    select(
                        temperature_readings.c.store_id,
                        temperature_readings.c.temperature,
                        temperature_readings.c.recorded_at,
                    ).where(
                        temperature_readings.c.recorded_at >= bucket,
                        temperature_readings.c.recorded_at < window_end,
                    )
                )
            ).all()

            readings_by_store: dict = defaultdict(list)
            for store_id, temperature, recorded_at in reading_rows:
                readings_by_store[store_id].append((float(temperature), recorded_at))

            if not readings_by_store:
                continue

            async with aggregates_session_factory() as agg_session:
                for store_id, readings in readings_by_store.items():
                    for product_id, tracked_since in products_by_store.get(store_id, []):
                        applicable_temps = [temp for temp, recorded_at in readings if recorded_at >= tracked_since]
                        if not applicable_temps:
                            # Every reading in this window predates this
                            # product being added to the store — nothing to
                            # attribute to it yet.
                            continue
                        avg, lo, hi, count = full_stats(applicable_temps)
                        row = await agg_session.get(HourlyAggregate, (store_id, product_id, bucket))
                        if row is None:
                            agg_session.add(
                                HourlyAggregate(
                                    store_id=store_id,
                                    product_id=product_id,
                                    hour_bucket=bucket,
                                    avg_temperature=avg,
                                    min_temperature=lo,
                                    max_temperature=hi,
                                    reading_count=count,
                                )
                            )
                        else:
                            row.avg_temperature = avg
                            row.min_temperature = lo
                            row.max_temperature = hi
                            row.reading_count = count
                        written += 1
                await agg_session.commit()

    return written


async def run_backfill_loop(
    aggregates_session_factory: async_sessionmaker,
    telemetry_session_factory: async_sessionmaker,
    interval_minutes: float,
) -> None:
    try:
        while True:
            try:
                await run_backfill_once(aggregates_session_factory, telemetry_session_factory)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("backfill cycle failed — will retry next interval")
            await asyncio.sleep(interval_minutes * 60)
    except asyncio.CancelledError:
        raise
