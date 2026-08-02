import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum as SAEnum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from security.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthType(str, enum.Enum):
    fingerprint = "fingerprint"
    nfc = "nfc"


# One shared SAEnum instance reused across both columns below — a second
# separately-constructed SAEnum with the same name would try to CREATE TYPE
# auth_type twice when both tables are created in the same migration.
AUTH_TYPE_ENUM = SAEnum(
    AuthType,
    name="auth_type",
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class User(Base):
    """One row per registered employee (fingerprint, AS608) or supplier
    (NFC, MFRC-522) — auth_type discriminates which hardware/credential
    shape applies. `credential` is the fingerprint template (base64) or the
    NFC card UID string; deliberately never exposed via UserRead."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    auth_type: Mapped[AuthType] = mapped_column(AUTH_TYPE_ENUM, nullable=False)
    credential: Mapped[str] = mapped_column(String, nullable=False)
    # JSON list of UUID strings rather than Postgres ARRAY — keeps the
    # column portable to the in-memory SQLite used by tests (see
    # telemetry's OutboxEvent.payload for the same JSON-over-ARRAY
    # convention). access_rules is the normalized join actually used by
    # POST /auth/*; this column is what admins read/write and is kept in
    # sync with it (see routers/users.py's _sync_access_rules).
    warehouse_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    access_rules: Mapped[list["AccessRule"]] = relationship(back_populates="user")


class Warehouse(Base):
    """Mirrors Inventory's Stock.id — same lazy-create pattern as
    Telemetry's Store: no separate "warehouse created" event to sync from,
    a row is lazily upserted the first time an auth attempt names a given
    id (see security/warehouses.py)."""

    __tablename__ = "warehouses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class AccessRule(Base):
    __tablename__ = "access_rules"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id"), primary_key=True)

    user: Mapped["User"] = relationship(back_populates="access_rules")


class VisitLog(Base):
    __tablename__ = "visit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id"), nullable=False, index=True)
    # Null when the credential itself matched no user at all (unknown
    # fingerprint template / card UID) — every other denial reason still
    # has a resolved user_id.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    auth_type: Mapped[AuthType] = mapped_column(AUTH_TYPE_ENUM, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    video_url: Mapped[str | None] = mapped_column(String, nullable=True)
    denial_reason: Mapped[str | None] = mapped_column(String, nullable=True)
