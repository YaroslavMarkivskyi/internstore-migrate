import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from security.models import AuthType


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    auth_type: AuthType
    credential: str = Field(min_length=1)
    warehouse_ids: list[uuid.UUID] = Field(default_factory=list)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None
    warehouse_ids: list[uuid.UUID] | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    auth_type: AuthType
    # credential is deliberately never returned — it's a biometric
    # template / raw card UID, not display data.
    warehouse_ids: list[uuid.UUID]
    is_active: bool
    created_at: datetime


class WarehouseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class WarehouseUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class VisitLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    warehouse_id: uuid.UUID
    user_id: uuid.UUID | None
    auth_type: AuthType
    success: bool
    attempted_at: datetime
    video_url: str | None
    denial_reason: str | None


class FingerprintAuthRequest(BaseModel):
    warehouse_id: uuid.UUID
    fingerprint_template: str


class NfcAuthRequest(BaseModel):
    warehouse_id: uuid.UUID
    card_uid: str


class AuthResult(BaseModel):
    allowed: bool
    user_id: uuid.UUID | None = None
    denial_reason: str | None = None
