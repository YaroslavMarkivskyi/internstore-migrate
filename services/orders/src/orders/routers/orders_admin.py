import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from orders.auth import InternalClaims, require_admin, require_admin_or_assistant
from orders.db import get_session
from orders.models import Order
from orders.schemas import OrderAdminRead, OrderRead

# nginx's /api/orders/ location strips the whole "/api/orders/" prefix
# before forwarding (see nginx.conf's `rewrite ^/api/orders/(.*)$ /$1
# break`), so the frontend's `orders/admin` call (relative to the
# /api/orders/ baseURL — see admin/orders.ts) arrives here as plain
# "/admin", not "/orders/admin". Customer-facing orders.py's "/orders"
# prefix looks doubled for the same reason: the frontend calls
# `orders/orders` (see public/orders.ts).
router = APIRouter(prefix="/admin", tags=["orders-admin"])


def _to_admin_read(order: Order) -> OrderAdminRead:
    return OrderAdminRead(**OrderRead.model_validate(order).model_dump(), customer=order.owner_id)


@router.get("", response_model=list[OrderAdminRead])
async def list_orders_admin(
    claims: Annotated[InternalClaims, Depends(require_admin_or_assistant)],
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: str | None = None,
) -> list[OrderAdminRead]:
    # owner_id lets the AI Assistant (role "assistant") pull one customer's
    # order history for chat context — an admin can also use it, but
    # normally browses unfiltered.
    query = select(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc())
    if owner_id is not None:
        query = query.where(Order.owner_id == owner_id)
    result = await session.execute(query)
    return [_to_admin_read(order) for order in result.scalars().all()]


@router.get("/{order_id}", response_model=OrderAdminRead)
async def get_order_admin(
    order_id: uuid.UUID,
    claims: Annotated[InternalClaims, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderAdminRead:
    result = await session.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _to_admin_read(order)
