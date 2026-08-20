import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from security.db import get_session
from security.models import AuthType, VisitLog
from security.schemas import VisitLogRead

router = APIRouter(prefix="/visit-log", tags=["visit-log"])

# No role checks in this router: admin-only in full (including its own GET
# route) -- enforced ahead of this app entirely, see users.py's own
# comment.


@router.get("", response_model=list[VisitLogRead])
async def list_visit_log(
    session: Annotated[AsyncSession, Depends(get_session)],
    warehouse_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    auth_type: AuthType | None = None,
    success: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[VisitLog]:
    stmt = select(VisitLog)
    if warehouse_id is not None:
        stmt = stmt.where(VisitLog.warehouse_id == warehouse_id)
    if user_id is not None:
        stmt = stmt.where(VisitLog.user_id == user_id)
    if auth_type is not None:
        stmt = stmt.where(VisitLog.auth_type == auth_type)
    if success is not None:
        stmt = stmt.where(VisitLog.success == success)
    if date_from is not None:
        stmt = stmt.where(VisitLog.attempted_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(VisitLog.attempted_at <= date_to)
    result = await session.execute(stmt.order_by(VisitLog.attempted_at.desc()))
    return list(result.scalars().all())
