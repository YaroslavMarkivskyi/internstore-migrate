import uuid

from pydantic import BaseModel

from payments.models import PaymentStatus


class ChargeRequest(BaseModel):
    order_id: uuid.UUID
    amount: float
    payment_method: str


class ChargeResponse(BaseModel):
    payment_id: uuid.UUID
    status: PaymentStatus


class RefundRequest(BaseModel):
    payment_id: uuid.UUID


class RefundResponse(BaseModel):
    status: PaymentStatus
