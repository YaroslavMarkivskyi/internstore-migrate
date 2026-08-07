import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from orders.auth import InternalClaims, get_internal_claims
from orders.authz import AuthzClient, get_authz_client
from orders.db import get_session
from orders.models import Order
from orders.schemas import OrderRead

router = APIRouter(prefix="/orders", tags=["orders"])


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
    authz: Annotated[AuthzClient, Depends(get_authz_client)],
) -> Order:
    result = await session.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # STR-140: OPA replaces the previous inline `order.owner_id !=
    # claims.sub` check (see policies/orders.rego's customer-owns-resource
    # rule) -- still 404, not 403, for a denied check: don't leak the
    # existence of other users' orders via a 403-vs-404 status difference.
    allowed = await authz.check(
        subject={"role": claims.role, "sub": claims.sub},
        action="view",
        resource={"type": "order", "owner": order.owner_id},
    )
    if not allowed:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
