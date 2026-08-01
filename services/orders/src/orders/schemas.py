import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from orders.models import OrderStatus


class CartItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(gt=0)


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CartItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    quantity: int


class CartRead(BaseModel):
    items: list[CartItemRead]


class CheckoutRequest(BaseModel):
    contact_name: str = Field(min_length=1, max_length=255)
    contact_email: str = Field(min_length=1, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=50)
    payment_method: str = Field(min_length=1, max_length=50)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    quantity: int


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: OrderStatus
    contact_name: str
    contact_email: str
    contact_phone: str | None
    payment_method: str
    created_at: datetime
    items: list[OrderItemRead]


class CheckoutInsufficientStockItem(BaseModel):
    product_id: uuid.UUID
    requested: int
    available: int
    sufficient: bool


class CheckoutInsufficientStockResponse(BaseModel):
    detail: str = "Insufficient stock for one or more items"
    items: list[CheckoutInsufficientStockItem]


class InventoryUnavailableResponse(BaseModel):
    detail: str = "Inventory temporarily unavailable, please retry"
    retry_after_seconds: int = 5
