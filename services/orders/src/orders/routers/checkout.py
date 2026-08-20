from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from orders.auth import InternalClaims, get_internal_claims
from orders.db import get_session
from orders.inventory_client import InventoryClient, InventoryUnavailableError, get_inventory_client
from orders.models import Cart, Order, OrderItem
from orders.outbox import add_outbox_event
from orders.schemas import (
    CheckoutInsufficientStockItem,
    CheckoutInsufficientStockResponse,
    CheckoutRequest,
    InventoryUnavailableResponse,
    OrderRead,
)

router = APIRouter(tags=["checkout"])

# claims here come from orders-gate's forwarded X-User-Id/X-User-Role (see
# orders/auth.py) -- already-verified identity, not this service's own
# jwt.decode() anymore. No admin/customer/guest role check needed on this
# route itself: orders-gate's default tier is "any authenticated caller",
# which is exactly this route's own access rule (see
# nginx/internal-gate/orders.conf).


@router.post("/checkout", response_model=OrderRead, status_code=201)
async def checkout(
    payload: CheckoutRequest,
    request: Request,
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
    inventory_client: Annotated[InventoryClient, Depends(get_inventory_client)],
) -> OrderRead | JSONResponse:
    result = await session.execute(
        select(Cart).options(selectinload(Cart.items)).where(Cart.owner_id == claims.sub)
    )
    cart = result.scalar_one_or_none()
    if cart is None or not cart.items:
        raise HTTPException(status_code=422, detail="Cart is empty")

    # check-availability is read-only — it doesn't reserve or decrement any
    # stock. Actual reservation is the future saga ticket's job; here we
    # only refuse to create an Order when we already know it can't be
    # fulfilled.
    internal_token = request.headers.get("x-internal-token", "")
    try:
        availability = await inventory_client.check_availability(
            [{"product_id": str(item.product_id), "quantity": item.quantity} for item in cart.items],
            internal_token,
        )
    except InventoryUnavailableError:
        return JSONResponse(status_code=503, content=InventoryUnavailableResponse().model_dump())

    if not availability["sufficient"]:
        return JSONResponse(
            status_code=409,
            content=CheckoutInsufficientStockResponse(
                items=[CheckoutInsufficientStockItem(**item) for item in availability["items"]]
            ).model_dump(mode="json"),
        )

    order = Order(
        owner_id=claims.sub,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        payment_method=payload.payment_method,
    )
    order.items = [OrderItem(product_id=item.product_id, quantity=item.quantity) for item in cart.items]
    session.add(order)

    for item in list(cart.items):
        await session.delete(item)

    # Flush so order.id (a Python-side default, only assigned at INSERT
    # time) is populated before we build the outbox payload referencing it.
    await session.flush()

    # Same transaction as the Order insert — the outbox pattern's whole
    # point is that Postgres's atomicity, not a second network call, is
    # what guarantees this event is never lost.
    add_outbox_event(
        session,
        "OrderCreated",
        {
            "order_id": str(order.id),
            "owner_id": order.owner_id,
            "contact_email": order.contact_email,
            "contact_name": order.contact_name,
            "items": [{"product_id": str(item.product_id), "quantity": item.quantity} for item in order.items],
        },
    )

    await session.commit()
    await session.refresh(order, attribute_names=["items"])
    return order
