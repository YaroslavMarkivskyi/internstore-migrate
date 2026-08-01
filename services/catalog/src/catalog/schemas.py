import uuid

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=3, max_length=15)


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=250)
    price: float = Field(gt=0)
    category_id: uuid.UUID
    description: str | None = Field(default=None, max_length=500)
    min_temperature: float | None = None
    max_temperature: float | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    price: float
    category_id: uuid.UUID
    description: str | None
    min_temperature: float | None
    max_temperature: float | None
