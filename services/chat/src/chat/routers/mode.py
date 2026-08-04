from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from chat.auth import InternalClaims, get_internal_claims
from chat.db import get_session
from chat.models import Room
from chat.outbox import add_outbox_event

router = APIRouter(prefix="/rooms", tags=["mode"])

# Fast-path cache TTL for chat:{room_id}:mode — "room lifetime" per the
# ticket. There's no explicit room-expiry concept in this service (rooms
# persist indefinitely once created), so this is a generous cap that just
# keeps a long-idle room's cache entry from lingering in Redis forever; the
# `rooms.ai_mode` column is the source of truth this key is re-derived from,
# so an expired key never loses the actual mode decision.
MODE_TTL_SECONDS = 7 * 24 * 60 * 60


class ModeUpdate(BaseModel):
    mode: Literal["ai", "human"]


def _room_owner_matches(role: str, room_id: str, sub: str) -> bool:
    # "assistant" can toggle any room, same as admin — needed for the AI
    # Assistant's own rate-limit fallback (auto-switch to human once
    # AI_RATE_LIMIT responses have been sent in a room).
    return role in ("admin", "assistant") or room_id == f"room_{sub}"


def _mode_key(room_id: str) -> str:
    return f"chat:{room_id}:mode"


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


@router.get("/{room_id}/mode")
async def get_mode(
    room_id: str,
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    if not _room_owner_matches(claims.role, room_id, claims.sub):
        raise HTTPException(status_code=403, detail="Not your room")

    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    return {"mode": "ai" if room.ai_mode else "human"}


@router.patch("/{room_id}/mode")
async def update_mode(
    room_id: str,
    payload: ModeUpdate,
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict:
    if not _room_owner_matches(claims.role, room_id, claims.sub):
        raise HTTPException(status_code=403, detail="Not your room")

    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    room.ai_mode = payload.mode == "ai"

    if payload.mode == "human":
        add_outbox_event(session, "AdminRequested", {"room_id": room_id})
    else:
        add_outbox_event(session, "AIModeEnabled", {"room_id": room_id})

    await session.commit()
    await redis.set(_mode_key(room_id), payload.mode, ex=MODE_TTL_SECONDS)

    return {"mode": payload.mode}
