import uuid
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from orders.auth import InternalClaims, get_internal_claims
from orders.catalog_client import CatalogClient, CatalogUnavailableError, get_catalog_client
from orders.db import get_session
from orders.models import Order, OrderStatus
from orders.payment_service import OrderNotPayableError, mark_order_paid
from orders.schemas import PaymentIntentRead
from orders.stripe_client import StripeClient, get_stripe_client

router = APIRouter(prefix="/orders", tags=["payments"])

# Separate, unprefixed router: nginx's /api/orders/ location strips the
# whole "/api/orders/" prefix (see nginx.conf), so a webhook URL configured
# in the Stripe dashboard as https://.../api/orders/webhooks/stripe arrives
# here as plain "/webhooks/stripe" -- not "/orders/webhooks/stripe" like
# router above. Also exempted from nginx's auth_request gate via a
# dedicated `location =` block, since Stripe has no internal token to send.
webhook_router = APIRouter(tags=["payments"])


@router.post("/{order_id}/payment-intent", response_model=PaymentIntentRead)
async def create_payment_intent(
    order_id: uuid.UUID,
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
    catalog_client: Annotated[CatalogClient, Depends(get_catalog_client)],
    stripe_client: Annotated[StripeClient, Depends(get_stripe_client)],
) -> PaymentIntentRead:
    result = await session.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    # Same 404-for-both convention as GET /orders/:id.
    if order is None or order.owner_id != claims.sub:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.payment_method != "card":
        raise HTTPException(status_code=422, detail="Order was not placed with card payment")
    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Order must be pending to pay, currently {order.status.value}")

    # Priced server-side from Catalog's *current* price, never from
    # anything the client sends — Orders keeps no price snapshot of its own
    # (see OrderItem in models.py), and trusting a client-supplied amount
    # for a payment charge would let a buyer pay whatever they want.
    try:
        total = 0.0
        for item in order.items:
            price = await catalog_client.get_product_price(str(item.product_id))
            total += price * item.quantity
    except CatalogUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Catalog temporarily unavailable, please retry") from exc

    amount_cents = round(total * 100)
    try:
        intent = await stripe_client.create_payment_intent(amount_cents=amount_cents, order_id=str(order.id))
    except stripe.APIError as exc:
        # Same idempotency_key (order-{id}-payment-intent, see
        # stripe_client.py) fired twice concurrently for this order -- e.g.
        # React StrictMode's dev-mode double effect invocation, or just a
        # double-click racing an in-flight request. Stripe rejects the
        # second one outright rather than queuing it ("another in-progress
        # request using this Idempotent Key"), which isn't a real failure —
        # respond the same way as "not pending yet" so the caller's
        # existing 409 retry loop (createPaymentIntentWithRetry in
        # StripePaymentStep) just tries again a moment later.
        raise HTTPException(status_code=409, detail="Payment already being started, please retry") from exc

    order.stripe_payment_intent_id = intent.id
    await session.commit()

    return PaymentIntentRead(client_secret=intent.client_secret)


@webhook_router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    stripe_client: Annotated[StripeClient, Depends(get_stripe_client)],
    stripe_signature: Annotated[str | None, Header(alias="stripe-signature")] = None,
) -> dict[str, bool]:
    payload = await request.body()
    if stripe_signature is None:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = stripe_client.construct_webhook_event(payload, stripe_signature)
    except (stripe.SignatureVerificationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature") from exc

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        result = await session.execute(
            select(Order).options(selectinload(Order.items)).where(Order.stripe_payment_intent_id == intent["id"])
        )
        order = result.scalar_one_or_none()
        if order is not None:
            try:
                mark_order_paid(session, order)
            except OrderNotPayableError:
                # Redelivered event for an order that already moved past
                # pending (webhook retried after we'd already processed it,
                # or the reservation expired in the same window) -- treat
                # as a no-op, same idempotency stance as
                # consumers/inventory_events.py's _guarded_transition.
                pass
            await session.commit()

    # Stripe retries on anything but 2xx -- always ack once the signature
    # checks out, even for event types we don't handle, so it stops resending.
    return {"received": True}
