import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, false, ForeignKey, JSON, Numeric, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from catalog.db import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    min_temperature: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    max_temperature: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    # server_default so existing rows stay published/visible after the
    # migration that adds this column.
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true(), default=True)
    # Soft delete: DELETE /products/{id} only ever flips this, never removes
    # the row (see routers/products.py's delete_product) -- Inventory has no
    # copy of its own of product name/price, it joins stock_items against
    # this table client-side (stockService.ts), and a hard delete left it
    # with orphaned rows pointing at nothing, permanently blocking that
    # stock from ever being deleted with no way for an admin to even see
    # why. Every other consumer (Orders' historical pricing, Inventory's
    # join) keeps working against a soft-deleted row; only the Admin
    # Products list and the storefront are expected to filter this out.
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false(), default=False)

    category: Mapped["Category"] = relationship(back_populates="products")
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.created_at"
    )


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    # The object-storage object key (e.g. "{product_id}/{uuid}.jpg") -- the
    # only durable reference to the image this row keeps. There's no
    # `image`/public-URL column: the bucket is private (see
    # ObjectStorageClient's docstring), so every response that includes an
    # `image` URL signs one from this key on the spot (short TTL, never
    # persisted) rather than storing a link that would eventually 403.
    object_key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="images")


class OutboxEvent(Base):
    """Same transactional-outbox shape as Inventory/Orders' — written in the
    same transaction as the product change it announces, published by a
    background poller."""

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
