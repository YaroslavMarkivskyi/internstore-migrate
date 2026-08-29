import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.auth import InternalClaims, get_internal_claims
from chat.db import get_session
from chat.object_storage_client import ObjectStorageClient
from chat.object_storage_dep import get_object_storage_client
from chat.models import Room

router = APIRouter(prefix="/rooms", tags=["attachments"])

ALLOWED_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png"}
MAX_SIZE_BYTES = 20 * 1024 * 1024


def _authorize_room_access(room: Room, claims: InternalClaims) -> None:
    if claims.role == "admin":
        return
    owner_id = str(room.customer_id) if room.customer_id is not None else room.session_id
    if owner_id != claims.sub:
        raise HTTPException(status_code=403, detail="Not a participant in this room")


@router.post("/{room_id}/attachments")
async def upload_attachment(
    room_id: str,
    file: UploadFile,
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
    object_storage_client: Annotated[ObjectStorageClient, Depends(get_object_storage_client)],
) -> dict:
    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    _authorize_room_access(room, claims)

    extension = ALLOWED_CONTENT_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(status_code=422, detail="Only JPEG and PNG images are supported")

    body = await file.read(MAX_SIZE_BYTES + 1)
    if len(body) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=422, detail="Attachment exceeds the 20MB limit")

    key = f"{room_id}/{uuid.uuid4()}.{extension}"
    await object_storage_client.put_object(key, body, file.content_type)
    # attachment_key is what the client sends back over the WS message that
    # actually posts this into a room (see ws/room.py) -- attachment_url
    # here is only a short-lived convenience so the client can show a
    # preview of what it just uploaded before sending; it's never stored.
    return {
        "attachment_key": key,
        "attachment_url": await object_storage_client.generate_presigned_url(key),
    }
