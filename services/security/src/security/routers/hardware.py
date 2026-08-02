import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from security.camera import build_video_url
from security.config import Settings
from security.db import get_session
from security.models import AccessRule, AuthType, User, VisitLog
from security.schemas import AuthResult, FingerprintAuthRequest, NfcAuthRequest
from security.warehouses import get_or_create_warehouse

router = APIRouter(prefix="/auth", tags=["auth"])


async def _authenticate(
    session: AsyncSession,
    settings: Settings,
    auth_type: AuthType,
    credential: str,
    warehouse_id: uuid.UUID,
) -> AuthResult:
    # No auth dependency: called directly by the hardware simulator
    # (fingerprint reader / NFC reader), not through a logged-in admin
    # session — same trust model as Telemetry's POST /measurements.
    await get_or_create_warehouse(session, warehouse_id)

    user = (
        await session.execute(select(User).where(User.auth_type == auth_type, User.credential == credential))
    ).scalar_one_or_none()

    user_id: uuid.UUID | None = None
    denial_reason: str | None = None
    allowed = False

    if user is None:
        denial_reason = "unknown credential"
    elif not user.is_active:
        user_id = user.id
        denial_reason = "inactive user"
    else:
        user_id = user.id
        has_access = (
            await session.execute(
                select(AccessRule).where(AccessRule.user_id == user.id, AccessRule.warehouse_id == warehouse_id)
            )
        ).scalar_one_or_none() is not None
        if has_access:
            allowed = True
        else:
            denial_reason = "no access to this warehouse"

    visit = VisitLog(
        warehouse_id=warehouse_id,
        user_id=user_id,
        auth_type=auth_type,
        success=allowed,
        denial_reason=denial_reason,
    )
    session.add(visit)
    await session.flush()
    visit.video_url = build_video_url(settings, visit.id)
    await session.commit()

    return AuthResult(allowed=allowed, user_id=user_id, denial_reason=denial_reason)


@router.post("/fingerprint", response_model=AuthResult)
async def auth_fingerprint(
    payload: FingerprintAuthRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResult:
    settings: Settings = request.app.state.settings
    return await _authenticate(
        session, settings, AuthType.fingerprint, payload.fingerprint_template, payload.warehouse_id
    )


@router.post("/nfc", response_model=AuthResult)
async def auth_nfc(
    payload: NfcAuthRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResult:
    settings: Settings = request.app.state.settings
    return await _authenticate(session, settings, AuthType.nfc, payload.card_uid, payload.warehouse_id)
