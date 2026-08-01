import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from inventory.db import Base


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # Populated by a Telemetry subscription that doesn't exist yet — left
    # null/pending until that integration lands (see task scope notes).
    temperature: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    items: Mapped[list["StockItem"]] = relationship(back_populates="stock")


class StockItem(Base):
    __tablename__ = "stock_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    stock_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    # References Catalog's Product.id. No FK — Catalog owns its own database
    # and Inventory only ever stores the referenced ID.
    product_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Held by RESERVED reservations; not yet decremented from `quantity`.
    # Available-for-new-reservation is `quantity - reserved_quantity`.
    #
    # Known, accepted limitation: `check-availability` (checkout's
    # pre-check) still sums raw `quantity`, blind to this column — see
    # docs/EVENT_BROKER.md. Reservation itself never oversells; this only
    # means checkout can optimistically pass its pre-check and still land
    # Rejected once the real reservation accounts for stock already held.
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Set by the telemetry-events consumer on TemperatureThresholdViolated;
    # never cleared automatically — an admin restocking/replacing the item
    # is expected to address it (no TemperatureNormalized handling here).
    is_unavailable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    stock: Mapped["Stock"] = relationship(back_populates="items")


class ReservationStatus(str, enum.Enum):
    RESERVED = "reserved"
    CONSUMED = "consumed"
    RELEASED = "released"


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # One reservation per Order — a duplicate OrderCreated is caught by
    # processed_events before try_reserve is ever called again, but the
    # unique constraint is a second line of defense.
    order_id: Mapped[uuid.UUID] = mapped_column(unique=True, nullable=False, index=True)
    status: Mapped[ReservationStatus] = mapped_column(
        SAEnum(
            ReservationStatus,
            name="reservation_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ReservationStatus.RESERVED,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    items: Mapped[list["ReservationItem"]] = relationship(back_populates="reservation", cascade="all, delete-orphan")


class ReservationItem(Base):
    __tablename__ = "reservation_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reservation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reservations.id"), nullable=False)
    stock_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stock_items.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    reservation: Mapped["Reservation"] = relationship(back_populates="items")


class ProcessedEvent(Base):
    """Dedup ledger for at-least-once Kafka delivery: an event_id present
    here has already had its side effects applied, so a redelivery is a
    no-op rather than a double reservation/decrement."""

    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxEvent(Base):
    """Same transactional-outbox shape as Orders' — written in the same
    transaction as the reservation/decrement/release it announces, published
    by a background poller. Without this, a crash between committing the
    reservation change and publishing the event would leave Inventory's
    state correct but Orders never finding out, stranding the Order."""

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
