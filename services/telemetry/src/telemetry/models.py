import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from telemetry.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Store(Base):
    """A warehouse/store. `id` is always assigned explicitly to match
    Inventory's `Stock.id` — Telemetry never mints its own store identity,
    it lazily upserts a row here (`stores.get_or_create_store`) the first
    time it sees a given id via `POST /measurements` or an inventory-events
    message."""

    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    threshold_temp: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    readings: Mapped[list["TemperatureReading"]] = relationship(back_populates="store")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="store")


class TemperatureReading(Base):
    __tablename__ = "temperature_readings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    temperature: Mapped[float] = mapped_column(Numeric, nullable=False)
    humidity: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    # Client-side default (not server_default) for microsecond precision —
    # SQLite's CURRENT_TIMESTAMP only has 1s resolution, which makes
    # "latest reading" ordering ambiguous for readings inserted in quick
    # succession (as the simulator and rapid API calls both do).
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    store: Mapped["Store"] = relationship(back_populates="readings")


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    # References Catalog's Product.id. No FK — Telemetry only ever stores
    # the referenced ID, same cross-service convention as Inventory's
    # StockItem.product_id.
    product_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    temperature_at_outbreak: Mapped[float] = mapped_column(Numeric, nullable=False)
    deviation: Mapped[float] = mapped_column(Numeric, nullable=False)

    store: Mapped["Store"] = relationship(back_populates="incidents")


class StoreProductThreshold(Base):
    """Local cache built from catalog-events (ProductThresholdUpdated) and
    inventory-events (ItemAdded) — never the source of truth, always
    rebuildable from those event streams."""

    __tablename__ = "store_product_thresholds"

    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    max_temp: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProcessedEvent(Base):
    """Dedup ledger for at-least-once Kafka delivery: an event_id present
    here has already had its side effects applied, so a redelivery is a
    no-op."""

    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxEvent(Base):
    """Same transactional-outbox shape as Catalog/Inventory/Orders' —
    written in the same transaction as the incident it announces, published
    by a background poller."""

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
