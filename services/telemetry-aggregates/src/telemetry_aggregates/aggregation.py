"""Pure aggregation math shared by the incremental consumer and the
backfill job, so both paths compute "the average" the same way. No I/O
here — keeps the arithmetic trivially unit-testable in isolation."""

from datetime import datetime, timezone


def truncate_to_hour(dt: datetime) -> datetime:
    """Bucket boundary for hourly_aggregates.hour_bucket. Naive datetimes
    are assumed UTC (matches telemetry's TemperatureReading.recorded_at,
    which is always timezone-aware UTC in practice, but event payloads
    cross a JSON boundary so we don't trust that blindly)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.replace(minute=0, second=0, microsecond=0)


def incremental_merge(
    old_avg: float, old_min: float, old_max: float, old_count: int, new_temp: float
) -> tuple[float, float, float, int]:
    """Simple incremental mean update over the event payload alone — no
    read-back to telemetry-db. `new_avg = (old_avg * old_count + new_temp)
    / (old_count + 1)`; min/max via pairwise comparison; count + 1. See the
    service README's "Incremental update path" section for why this
    (rather than a cross-database join per event) is the deliberate
    choice."""
    new_count = old_count + 1
    new_avg = (old_avg * old_count + new_temp) / new_count
    new_min = min(old_min, new_temp)
    new_max = max(old_max, new_temp)
    return new_avg, new_min, new_max, new_count


def full_stats(temperatures: list[float]) -> tuple[float, float, float, int]:
    """Ground-truth avg/min/max/count over a complete set of readings —
    what backfill.py computes directly from telemetry-db's raw table for a
    given `{store, product, hour}`. Never called with an empty list."""
    count = len(temperatures)
    return sum(temperatures) / count, min(temperatures), max(temperatures), count
