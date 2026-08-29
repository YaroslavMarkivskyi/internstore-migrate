import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.db import get_session
from chat.models import Message, Room, RoomMember, SenderType
from chat.object_storage_client import ObjectStorageClient
from chat.object_storage_dep import get_object_storage_client, resolve_attachment_url

router = APIRouter(prefix="/rooms", tags=["rooms"])

# No role checks in this router anymore: GET /rooms is admin-only, GET
# /rooms/{id}/messages is admin-or-assistant, DELETE /rooms/{id} is
# admin-only -- all enforced ahead of this app entirely by chat-gate
# (nginx, auth_request) + chat-verify (OPA-backed, policies/chat.rego).
# See docker-compose.yml's chat-gate/chat-verify and
# nginx/internal-gate/chat.conf's $chat_auth_tier map.


@router.get("")
async def list_rooms(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    rooms = (
        (await session.execute(select(Room).order_by(Room.last_message_at.desc().nullslast())))
        .scalars()
        .all()
    )

    items = []
    for room in rooms:
        last_message = (
            await session.execute(
                select(Message).where(Message.room_id == room.id).order_by(Message.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()

        # "Unread" has no dedicated read-receipt table — approximated as
        # customer messages since the most recent admin to join this room
        # (room_members.joined_at), or all customer messages if no admin
        # has ever joined. A real per-admin read cursor is out of scope.
        last_joined_at = (
            await session.execute(select(func.max(RoomMember.joined_at)).where(RoomMember.room_id == room.id))
        ).scalar_one()
        unread_query = select(func.count()).where(
            Message.room_id == room.id, Message.sender_type == SenderType.CUSTOMER
        )
        if last_joined_at is not None:
            unread_query = unread_query.where(Message.created_at > last_joined_at)
        unread_count = (await session.execute(unread_query)).scalar_one()

        items.append(
            {
                "id": room.id,
                # No customer directory in this service — see README's
                # dev-gaps section. Consumers resolve a display name from
                # customer_id/session_id themselves if needed.
                "customer_name": None,
                "unread_count": unread_count,
                "last_message": last_message.content if last_message else None,
                "last_message_at": room.last_message_at,
            }
        )

    return {"rooms": items}


@router.get("/{room_id}/messages")
async def get_messages(
    room_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    object_storage_client: Annotated[ObjectStorageClient, Depends(get_object_storage_client)],
    before: str | None = None,
    limit: int = 50,
) -> dict:
    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    query = select(Message).where(Message.room_id == room_id)
    if before is not None:
        try:
            cursor_id = uuid.UUID(before)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid cursor") from None
        cursor_message = await session.get(Message, cursor_id)
        if cursor_message is not None:
            query = query.where(Message.created_at < cursor_message.created_at)
    query = query.order_by(Message.created_at.desc()).limit(limit)

    messages = (await session.execute(query)).scalars().all()
    return {
        "messages": [
            {
                "id": str(message.id),
                "sender_type": message.sender_type.value,
                "sender_id": message.sender_id,
                "content": message.content,
                "attachment_url": await resolve_attachment_url(object_storage_client, message.attachment_key),
                "created_at": message.created_at,
            }
            for message in messages
        ]
    }


@router.delete("/{room_id}", status_code=204)
async def delete_room(
    room_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    await session.execute(delete(Message).where(Message.room_id == room_id))
    await session.execute(delete(RoomMember).where(RoomMember.room_id == room_id))
    await session.delete(room)
    await session.commit()
