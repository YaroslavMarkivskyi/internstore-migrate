import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from orders.auth import InternalClaims, get_internal_claims
from orders.db import get_session
from orders.models import Order
from orders.payment_service import OrderNotPayableError, mark_order_paid
from orders.schemas import OrderRead

router = APIRouter(prefix="/orders", tags=["orders"])

# claims here come from orders-gate's forwarded X-User-Id/X-User-Role (see
# orders/auth.py) -- already-verified identity, not this service's own
# jwt.decode() anymore.


@router.post("/{order_id}/pay", response_model=OrderRead)
async def pay_order(
    order_id: uuid.UUID,
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Order:
    result = await session.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    # Same 404-for-both convention as GET /orders/:id — don't leak existence
    # of other users' orders.
    if order is None or order.owner_id != claims.sub:
        raise HTTPException(status_code=404, detail="Order not found")

    try:
        mark_order_paid(session, order)
    except OrderNotPayableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(order, attribute_names=["items"])
    return order
