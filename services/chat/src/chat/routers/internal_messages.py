from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from chat.auth import InternalClaims, require_assistant
from chat.db import get_session
from chat.models import Message, Room, SenderType
from chat.pubsub import PubSubRouter

router = APIRouter(prefix="/rooms", tags=["internal-messages"])


class InternalMessageCreate(BaseModel):
    content: str


def get_pubsub(request: Request) -> PubSubRouter:
    return request.app.state.pubsub


# The AI Assistant's only way to put a message into a room — same DB write +
# Redis pub/sub publish as a customer/admin sending over the WebSocket (see
# ws/room.py), just entered from a plain REST call since the assistant is a
# Kafka consumer, not a WS client. Every connected WS client for this room
# receives it in real time exactly like any other message.
@router.post("/{room_id}/messages", status_code=201)
async def post_internal_message(
    room_id: str,
    payload: InternalMessageCreate,
    claims: Annotated[InternalClaims, Depends(require_assistant)],
    session: Annotated[AsyncSession, Depends(get_session)],
    pubsub: Annotated[PubSubRouter, Depends(get_pubsub)],
) -> dict:
    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    now = datetime.now(timezone.utc)
    message = Message(
        room_id=room_id,
        sender_type=SenderType.ASSISTANT,
        sender_id="ai-assistant",
        content=payload.content,
        created_at=now,
    )
    session.add(message)
    room.last_message_at = now
    await session.commit()
    await session.refresh(message)

    await pubsub.publish(
        room_id,
        {
            "type": "message",
            "room_id": room_id,
            "sender_type": SenderType.ASSISTANT.value,
            "sender_id": "ai-assistant",
            "content": payload.content,
            "attachment_url": None,
            "created_at": now.isoformat(),
        },
    )

    return {
        "id": str(message.id),
        "sender_type": message.sender_type.value,
        "sender_id": message.sender_id,
        "content": message.content,
        "created_at": message.created_at,
    }
