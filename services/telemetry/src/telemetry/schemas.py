import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MeasurementCreate(BaseModel):
    store_id: uuid.UUID
    temperature: float
    humidity: float | None = None


class MeasurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    temperature: float
    humidity: float | None
    recorded_at: datetime


class StoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    threshold_temp: float | None
    current_temperature: float | None = None
    has_open_violation: bool = False


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    threshold_temp: float | None = None


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    product_id: uuid.UUID
    started_at: datetime
    temperature_at_outbreak: float
    deviation: float
