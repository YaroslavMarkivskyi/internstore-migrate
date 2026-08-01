import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from telemetry.models import Incident, StoreProductThreshold, TemperatureReading
from telemetry.outbox import add_outbox_event

VIOLATION_WINDOW = timedelta(hours=1)
VIOLATION_MARGIN = 1  # degrees over max_temp before it counts as a violation


async def _has_coverage(session: AsyncSession, store_id, window_start: datetime) -> bool:
    """True if there's a reading at or before window_start, proving the
    window isn't just the first few minutes of data collection."""
    result = await session.execute(
        select(TemperatureReading.id)
        .where(TemperatureReading.store_id == store_id, TemperatureReading.recorded_at <= window_start)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _has_open_incident(session: AsyncSession, store_id, product_id, window_start: datetime) -> bool:
    result = await session.execute(
        select(Incident.id)
        .where(
            Incident.store_id == store_id,
            Incident.product_id == product_id,
            Incident.started_at >= window_start,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def check_violations(
    session: AsyncSession, now: datetime | None = None, window: timedelta = VIOLATION_WINDOW
) -> int:
    """Sustained-violation check, not an average: every reading in the
    window must exceed `max_temp + 1` for a violation to fire. A spike that
    dips back down mid-window is not a violation even if the mean is high
    (see EP-02/EP-09: "temperature is higher than the threshold by more
    than 1 degree for an hour"). `window` defaults to a full hour but is
    dev-configurable (see Settings.violation_window_seconds) so
    scripts/test-telemetry-saga.sh doesn't have to wait a real hour."""
    now = now or datetime.now(timezone.utc)
    window_start = now - window

    thresholds = list(
        (
            await session.execute(select(StoreProductThreshold).where(StoreProductThreshold.max_temp.is_not(None)))
        )
        .scalars()
        .all()
    )

    created = 0
    for threshold in thresholds:
        if not await _has_coverage(session, threshold.store_id, window_start):
            continue

        readings = list(
            (
                await session.execute(
                    select(TemperatureReading)
                    .where(
                        TemperatureReading.store_id == threshold.store_id,
                        TemperatureReading.recorded_at >= window_start,
                        TemperatureReading.recorded_at <= now,
                    )
                    .order_by(TemperatureReading.recorded_at)
                )
            )
            .scalars()
            .all()
        )
        if not readings:
            continue

        limit = float(threshold.max_temp) + VIOLATION_MARGIN
        if not all(float(r.temperature) > limit for r in readings):
            continue

        if await _has_open_incident(session, threshold.store_id, threshold.product_id, window_start):
            continue

        latest = readings[-1]
        deviation = float(latest.temperature) - float(threshold.max_temp)
        session.add(
            Incident(
                store_id=threshold.store_id,
                product_id=threshold.product_id,
                temperature_at_outbreak=float(latest.temperature),
                deviation=deviation,
            )
        )
        add_outbox_event(
            session,
            "TemperatureThresholdViolated",
            {
                "stock_id": str(threshold.store_id),
                "product_id": str(threshold.product_id),
                "temperature": float(latest.temperature),
                "deviation": deviation,
            },
        )
        created += 1

    return created


async def run_violation_checker(
    session_factory: async_sessionmaker, check_interval: float, window: timedelta = VIOLATION_WINDOW
) -> None:
    try:
        while True:
            async with session_factory() as session:
                await check_violations(session, window=window)
                await session.commit()
            await asyncio.sleep(check_interval)
    except asyncio.CancelledError:
        raise
