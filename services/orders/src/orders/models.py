import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum as SAEnum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orders.db import Base


class OrderStatus(str, enum.Enum):
    NEW = "new"
    PENDING = "pending"
    PAID = "paid"
    DONE = "done"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Either a real Firebase sub (customer/admin) or a guest_id (role=guest)
    # minted by auth-backend's guest-session fallback — Orders treats both
    # uniformly off the internal token's `sub` claim.
    owner_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "product_id", name="uq_cart_item_product"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cart_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("carts.id"), nullable=False)
    # References Catalog's Product.id. No FK — Catalog owns its own database,
    # same convention as inventory.StockItem.product_id.
    product_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    cart: Mapped["Cart"] = relationship(back_populates="items")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(
            OrderStatus,
            name="order_status",
            native_enum=True,
            # Bind/store the enum's .value ("new") rather than its .name
            # ("NEW") — matches the native Postgres type's member literal
            # created in migrations/versions/fd263b14ded7_*.py.
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=OrderStatus.NEW,
    )
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set by POST /orders/{id}/payment-intent when a "card" order starts
    # Stripe checkout; the webhook handler uses it to find which Order a
    # payment_intent.succeeded event belongs to (Stripe's metadata.order_id
    # would also work, but a DB lookup avoids trusting webhook payload
    # content for anything beyond "which PaymentIntent fired").
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")


class OutboxEvent(Base):
    """Transactional outbox: written in the same DB transaction as the
    domain change it announces, published to Kafka by a background poller
    that marks `published_at` once the send succeeds. Guarantees an event
    is never lost between commit and publish (at the cost of possible
    redelivery on a crash between publish and marking published — Inventory
    consumers must be idempotent)."""

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
