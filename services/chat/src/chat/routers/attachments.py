import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.auth import InternalClaims, get_internal_claims
from chat.db import get_session
from chat.minio_client import MinioClient
from chat.minio_dep import get_minio_client
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
    minio_client: Annotated[MinioClient, Depends(get_minio_client)],
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
    attachment_url = await minio_client.put_object(key, body, file.content_type)
    return {"attachment_url": attachment_url}
