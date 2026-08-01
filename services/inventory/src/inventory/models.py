import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String
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

    stock: Mapped["Stock"] = relationship(back_populates="items")
