import uuid

from pydantic import BaseModel, ConfigDict, Field


class StockCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    temperature: float | None = None
    humidity: float | None = None


class StockUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    temperature: float | None = None
    humidity: float | None = None


class StockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    temperature: float | None
    humidity: float | None


class StockItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stock_id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    is_unavailable: bool


class StockItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(gt=0)


class StockItemMove(BaseModel):
    to_stock_id: uuid.UUID
    quantity: int = Field(gt=0)


class StockItemQuantityUpdate(BaseModel):
    quantity: int = Field(ge=0)


class ConsolidatedItemRead(BaseModel):
    product_id: uuid.UUID
    quantity: int


class StockItemDetailRead(BaseModel):
    id: uuid.UUID
    stock_id: uuid.UUID
    product_id: uuid.UUID
    # The stock's name -- named `name` (not `stock_name`) so it matches the
    # frontend's IStockDetails.name with zero ccApi remapping, same trick
    # used for ProductImage.image in Catalog.
    name: str
    quantity: int
    temperature: float | None
    humidity: float | None


class AvailabilityRequestItem(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(gt=0)


class CheckAvailabilityRequest(BaseModel):
    items: list[AvailabilityRequestItem] = Field(min_length=1)


class AvailabilityResultItem(BaseModel):
    product_id: uuid.UUID
    requested: int
    available: int
    sufficient: bool


class CheckAvailabilityResponse(BaseModel):
    sufficient: bool
    items: list[AvailabilityResultItem]
