import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum as SAEnum, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chat.db import Base


class SenderType(str, enum.Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class Room(Base):
    """`id` is the business key itself (`room_{user_id}` for registered
    customers, `room_{session_id}` for guests) rather than a UUID surrogate —
    it's the exact string used for the WS path segment, the Redis channel
    name, and the presence-set keys, so a single key avoids a redundant
    lookup column everywhere else in this service."""

    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when an UnreadMessageReceived outbox event is staged for this room
    # (no admin online when a customer/guest message arrived), cleared again
    # when an admin connects — see ws/room.py. Gates re-notification: a
    # fresh round of offline messages after an admin has since come and
    # gone can notify again, but repeated messages within the same unread
    # window don't spam a second email.
    notification_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["Message"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    members: Mapped[list["RoomMember"]] = relationship(back_populates="room", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), nullable=False, index=True)
    sender_type: Mapped[SenderType] = mapped_column(
        SAEnum(
            SenderType,
            name="sender_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    # Keycloak sub for customer/admin. Guest messages are never persisted
    # (ephemeral, lost on disconnect — per the ticket, guest history isn't
    # kept), so sender_type is never "guest" here.
    sender_id: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped["Room"] = relationship(back_populates="messages")


class RoomMember(Base):
    """Tracks which admins have opened a room — first admin to open it
    "takes" it, others can join; no exclusivity is enforced."""

    __tablename__ = "room_members"

    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), primary_key=True)
    admin_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped["Room"] = relationship(back_populates="members")


class OutboxEvent(Base):
    """Transactional outbox: written in the same DB transaction as the
    domain change it announces, published to Kafka by a background poller
    that marks `published_at` once the send succeeds. Same pattern as
    services/orders/src/orders/models.py's OutboxEvent."""

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
