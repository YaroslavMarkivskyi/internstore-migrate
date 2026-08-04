import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from orders.auth import InternalClaims, require_admin, require_admin_or_assistant
from orders.db import get_session
from orders.models import Order, OrderStatus
from orders.payment_service import OrderNotPayableError, mark_order_paid
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


@router.post("/{order_id}/pay", response_model=OrderAdminRead)
async def pay_order_admin(
    order_id: uuid.UUID,
    claims: Annotated[InternalClaims, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderAdminRead:
    # Card orders go through Stripe (POST /orders/{id}/payment-intent +
    # webhook, see routers/payments.py) -- this is the manual counterpart
    # for cash_on_delivery, where there's no payment processor to confirm
    # for us and an admin/courier has to mark it paid by hand once the
    # cash is actually collected on delivery. Not restricted to
    # cash_on_delivery orders specifically: an admin overriding a stuck
    # card order is a legitimate, if rarer, use of the same action.
    result = await session.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    try:
        mark_order_paid(session, order)
    except OrderNotPayableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(order, attribute_names=["items"])
    return _to_admin_read(order)


@router.post("/{order_id}/ship", response_model=OrderAdminRead)
async def ship_order_admin(
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

    if order.status != OrderStatus.PAID:
        raise HTTPException(
            status_code=409, detail=f"Order must be paid to ship, currently {order.status.value}"
        )

    order.status = OrderStatus.DONE
    await session.commit()
    await session.refresh(order, attribute_names=["items"])
    return _to_admin_read(order)
