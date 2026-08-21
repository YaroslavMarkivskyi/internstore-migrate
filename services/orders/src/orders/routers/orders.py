import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from orders.auth import InternalClaims, get_internal_claims
from orders.db import get_session
from orders.models import Order
from orders.schemas import OrderRead

router = APIRouter(prefix="/orders", tags=["orders"])

# claims here come from orders-gate's forwarded X-User-Id/X-User-Role
# (see orders/auth.py) -- already-verified identity, not this service's
# own jwt.decode() anymore. get_order's per-order ownership check below
# is a plain comparison against the row it just SELECTed -- no OPA
# round-trip needed for that (owner_id lives in this service's own DB
# either way, so OPA couldn't have made that decision on its own).


@router.get("", response_model=list[OrderRead])
async def list_orders(
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Order]:
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.owner_id == claims.sub)
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: uuid.UUID,
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Order:
    result = await session.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # Admin bypasses ownership; everyone else may only see their own order.
    # Still 404, not 403, for a denied check: don't leak the existence of
    # other users' orders via a 403-vs-404 status difference.
    if claims.role != "admin" and order.owner_id != claims.sub:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
