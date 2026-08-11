import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from inventory.db import Base


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # Populated by a Telemetry subscription that doesn't exist yet — left
    # null/pending until that integration lands (see task scope notes).
    temperature: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    # Same status as temperature -- no Telemetry subscription populates this
    # yet, left null/pending until that integration lands.
    humidity: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    items: Mapped[list["StockItem"]] = relationship(back_populates="stock")


class StockItem(Base):
    """STR-149: this is now a read-model *projection*, not a source of
    truth. It is written exclusively by `projector.project_and_upsert`,
    inside the same DB transaction as the `stock_events` append that
    produced it -- never by direct UPDATE/INSERT from request-handling
    code. See `stock_events` (this file, below) and README.md's "Event
    sourcing" section.
    """

    __tablename__ = "stock_items"
    __table_args__ = (
        # Defense-in-depth, not load-bearing: the projector is the sole
        # writer and is already serialized per-aggregate by stock_events'
        # own UNIQUE(aggregate_id, sequence_number) (see event_store.py).
        # This just makes a projector bug loud instead of silently
        # producing two rows for one (stock_id, product_id) pair.
        UniqueConstraint("stock_id", "product_id", name="uq_stock_items_stock_product"),
    )

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


class StockEvent(Base):
    """STR-149: the append-only event log -- the sole source of truth for
    the `(stock_id, product_id)` aggregate. Never updated or deleted.
    `stock_items` (above) is a projection folded from this table; it is
    populated synchronously, in the same transaction as the row here, by
    `projector.project_and_upsert` -- see event_store.py and README.md.

    Two distinct tables, do not conflate: this is the event-sourcing log
    (new, STR-149). `OutboxEvent` (above) is the existing, unrelated
    inter-service Kafka pub/sub outbox (e.g. `StockReserved` notifications
    to Orders) and is unaffected by this migration.

    `UNIQUE(aggregate_id, sequence_number)` is the concurrency-control
    mechanism: appending requires knowing the aggregate's current last
    sequence_number and inserting at +1; a constraint violation means a
    concurrent writer already claimed that slot (see event_store.py). This
    is the load-bearing correctness mechanism for the reservation saga --
    it replaces the row-level locking a directly-mutated `stock_items`
    UPDATE would have relied on.
    """

    __tablename__ = "stock_events"
    __table_args__ = (UniqueConstraint("aggregate_id", "sequence_number", name="uq_stock_events_aggregate_sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # uuid5(AGGREGATE_NAMESPACE, f"{stock_id}:{product_id}") -- see
    # events.compute_aggregate_id. Deterministic, so any caller can address
    # a stream without a lookup table.
    aggregate_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Python-side default (not server_default=func.now()) deliberately --
    # the `as-of` endpoint filters on this column to reconstruct
    # point-in-time state, and SQLite's CURRENT_TIMESTAMP (what
    # server_default=func.now() compiles to there) only has second
    # resolution, which would make same-second events indistinguishable.
    # sequence_number remains the true ordering; created_at only needs to
    # be monotonic enough to place events relative to a wall-clock cutoff.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class StockSnapshot(Base):
    """STR-149: periodic snapshots, purely to bound replay cost -- NOT
    needed for the live projection's correctness or freshness (that's
    always current by construction, folded synchronously with every event
    append). Snapshots exist only for (a) disaster-recovery rebuild of
    `stock_items` from `stock_events`, and (b) bounding replay cost for the
    `as-of` point-in-time endpoint on aggregates with long histories. See
    snapshots.py and README.md.
    """

    __tablename__ = "stock_snapshots"

    aggregate_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # The sequence_number this snapshot represents state *as of* --
    # replaying stock_events WHERE aggregate_id = ... AND sequence_number >
    # this, starting from `state`, reproduces the live projection.
    sequence_number: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
