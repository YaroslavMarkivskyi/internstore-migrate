from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from chat.db import get_session
from chat.models import Message, Room, SenderType
from chat.pubsub import PubSubRouter

router = APIRouter(prefix="/rooms", tags=["internal-messages"])

# No role check in this router anymore: this route is assistant-only,
# enforced ahead of this app entirely by chat-gate + chat-verify. See
# routers/rooms.py's comment for the full pattern.


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


class StreamChunk(BaseModel):
    # One of: a delta (delta set, done/reset false), a reset (reset true), or
    # the end of stream (done true, content = the full assembled reply).
    stream_id: str
    delta: str | None = None
    content: str | None = None
    done: bool = False
    reset: bool = False


# STR-XXX: the streaming counterpart of post_internal_message above. The AI
# Assistant calls this repeatedly as Gemini produces the reply — each call
# fans a `message_delta` frame out to the room's WebSocket clients via the
# same Redis pub/sub path, so the customer sees the answer build up. Nothing
# is written to the DB until the final `done` call, which persists the whole
# assembled reply as one Message (exactly what post_internal_message would
# have stored) and publishes `message_done`. `reset` tells clients to drop a
# partial reply the model abandoned to call a tool.
@router.post("/{room_id}/messages/stream", status_code=202)
async def post_streamed_message(
    room_id: str,
    payload: StreamChunk,
    session: Annotated[AsyncSession, Depends(get_session)],
    pubsub: Annotated[PubSubRouter, Depends(get_pubsub)],
) -> dict:
    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    if payload.reset:
        await pubsub.publish(
            room_id, {"type": "message_reset", "room_id": room_id, "stream_id": payload.stream_id}
        )
        return {"status": "reset"}

    if not payload.done:
        await pubsub.publish(
            room_id,
            {
                "type": "message_delta",
                "room_id": room_id,
                "stream_id": payload.stream_id,
                "delta": payload.delta or "",
            },
        )
        return {"status": "delta"}

    content = (payload.content or "").strip()
    if not content:
        # Nothing to persist (agent produced no text) — just tell clients the
        # stream is over so they can clear any "typing" state.
        await pubsub.publish(
            room_id, {"type": "message_done", "room_id": room_id, "stream_id": payload.stream_id, "content": ""}
        )
        return {"status": "empty"}

    now = datetime.now(timezone.utc)
    message = Message(
        room_id=room_id,
        sender_type=SenderType.ASSISTANT,
        sender_id="ai-assistant",
        content=content,
        created_at=now,
    )
    session.add(message)
    room.last_message_at = now
    await session.commit()
    await session.refresh(message)

    await pubsub.publish(
        room_id,
        {
            "type": "message_done",
            "room_id": room_id,
            "stream_id": payload.stream_id,
            "sender_type": SenderType.ASSISTANT.value,
            "sender_id": "ai-assistant",
            "content": content,
            "attachment_url": None,
            "created_at": now.isoformat(),
        },
    )
    return {"status": "done", "id": str(message.id)}
