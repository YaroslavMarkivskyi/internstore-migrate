import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from telemetry_aggregates.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HourlyAggregate(Base):
    """The CQRS read model itself. Composite PK is the whole idempotency
    mechanism: both the incremental Kafka consumer's upsert and the
    backfill job's recompute-and-overwrite target the exact same row for a
    given `{store_id, product_id, hour_bucket}` — there is no way for the
    two paths to create divergent rows for the same hour. See README's
    "Idempotency guarantee" section for the full explanation, including its
    honest limits (this PK makes the *target* unambiguous; it does not by
    itself prevent transient double-counting from the incremental path
    after a consumer outage — that's what the periodic backfill overwrite
    is for)."""

    __tablename__ = "hourly_aggregates"

    store_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # References Catalog's Product.id, same bare-UUID-no-FK convention
    # telemetry itself uses for Incident.product_id.
    product_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # Always truncated to the hour, e.g. 2026-08-11 14:00:00 — see
    # aggregation.truncate_to_hour.
    hour_bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    avg_temperature: Mapped[float] = mapped_column(Numeric, nullable=False)
    min_temperature: Mapped[float] = mapped_column(Numeric, nullable=False)
    max_temperature: Mapped[float] = mapped_column(Numeric, nullable=False)
    reading_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class ProcessedEvent(Base):
    """Dedup ledger for the incremental consumer's at-least-once Kafka
    delivery — same pattern as telemetry's own `processed_events`. Guards
    against double-applying the *same* Kafka message; it does not (and
    can't, on its own) guard against the incremental path re-deriving a
    reading that backfill already incorporated after a consumer outage —
    see README."""

    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
