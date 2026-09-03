import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

# Money on the wire: keep the domain value a Decimal (matches the
# Numeric(10, 2) column and avoids binary-float rounding), but serialise it
# to a JSON number so the existing API contract is unchanged -- Pydantic
# would otherwise emit a Decimal as a JSON string. Python-mode dumps
# (model_dump()) still see the Decimal.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


class ORMModel(BaseModel):
    """Base for every response model read straight off a SQLAlchemy row."""

    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=3, max_length=15)


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=3, max_length=15)


class CategoryDeleteOptions(BaseModel):
    deletion_mode: Literal["move", "unpublish_and_delete"] | None = None
    target_category_id: uuid.UUID | None = None


class CategoryRead(ORMModel):
    id: uuid.UUID
    name: str


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=250)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    category_id: uuid.UUID
    description: str | None = Field(default=None, max_length=500)
    min_temperature: float | None = None
    max_temperature: float | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=250)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=500)
    min_temperature: float | None = None
    max_temperature: float | None = None
    is_published: bool | None = None


class ProductRead(ORMModel):
    id: uuid.UUID
    name: str
    price: Money
    category_id: uuid.UUID
    description: str | None
    min_temperature: float | None
    max_temperature: float | None
    is_published: bool
    is_deleted: bool


class ProductImageRead(ORMModel):
    id: uuid.UUID
    image: str
