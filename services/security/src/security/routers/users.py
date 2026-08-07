import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from security.auth import require_authz
from security.db import get_session
from security.models import AccessRule, AuthType, User
from security.schemas import UserCreate, UserRead, UserUpdate
from security.warehouses import get_or_create_warehouse

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_authz("manage", "user"))])


async def _sync_access_rules(session: AsyncSession, user_id: uuid.UUID, warehouse_ids: list[uuid.UUID]) -> None:
    # access_rules is a normalized join derived from users.warehouse_ids —
    # POST /auth/* joins against this table; admins only ever read/write
    # warehouse_ids, so it's kept in sync here rather than independently
    # editable. Granting access to a warehouse_id no hardware has reported
    # yet must still lazily create the Warehouse row, or the FK on
    # access_rules would reject it.
    await session.execute(delete(AccessRule).where(AccessRule.user_id == user_id))
    for warehouse_id in warehouse_ids:
        await get_or_create_warehouse(session, warehouse_id)
        session.add(AccessRule(user_id=user_id, warehouse_id=warehouse_id))


async def _get_user_or_404(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("", response_model=list[UserRead])
async def list_users(
    session: Annotated[AsyncSession, Depends(get_session)],
    auth_type: AuthType | None = None,
    is_active: bool | None = None,
) -> list[User]:
    stmt = select(User)
    if auth_type is not None:
        stmt = stmt.where(User.auth_type == auth_type)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    result = await session.execute(stmt.order_by(User.name))
    return list(result.scalars().all())


@router.post("", response_model=UserRead, status_code=201)
async def create_user(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    user = User(
        name=payload.name,
        auth_type=payload.auth_type,
        credential=payload.credential,
        warehouse_ids=[str(w) for w in payload.warehouse_ids],
    )
    session.add(user)
    await session.flush()
    await _sync_access_rules(session, user.id, payload.warehouse_ids)
    await session.commit()
    await session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    user = await _get_user_or_404(session, user_id)

    updates = payload.model_dump(exclude_unset=True)
    warehouse_ids = updates.pop("warehouse_ids", None)
    for field, value in updates.items():
        setattr(user, field, value)
    if warehouse_ids is not None:
        user.warehouse_ids = [str(w) for w in warehouse_ids]
        await _sync_access_rules(session, user.id, warehouse_ids)

    await session.commit()
    await session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await _get_user_or_404(session, user_id)
    await session.execute(delete(AccessRule).where(AccessRule.user_id == user_id))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()
