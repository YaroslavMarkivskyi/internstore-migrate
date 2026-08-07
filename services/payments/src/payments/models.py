import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from payments.db import Base


class PaymentStatus(str, enum.Enum):
    CHARGED = "charged"
    REFUNDED = "refunded"
    FAILED = "failed"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # References Orders' Order.id. No FK — Orders owns its own database and
    # Payments only ever stores the referenced ID, same as every other
    # cross-service reference in this codebase (see inventory's
    # StockItem.product_id comment).
    #
    # Unique — this is the idempotency key for POST /charge: a same-order_id
    # retry looks up and returns this row instead of charging twice.
    order_id: Mapped[uuid.UUID] = mapped_column(unique=True, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(
            PaymentStatus,
            name="payment_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
