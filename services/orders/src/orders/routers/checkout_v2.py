import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from temporalio.client import Client, WorkflowFailureError

from orders.auth import InternalClaims, get_internal_claims
from orders.catalog_client import CatalogClient, CatalogUnavailableError, get_catalog_client
from orders.db import get_session
from orders.models import Cart, Order, OrderItem
from orders.schemas import (
    CheckoutRequest,
    CheckoutV2Response,
    OrderRead,
    WorkflowOrderCreate,
    WorkflowOrderStatusUpdate,
)
from orders.temporal_client import get_temporal_client

router = APIRouter(tags=["checkout-v2"])

# Separate router for the internal endpoints checkout-workflow's Temporal
# activities call back into (create_order, update_order_status,
# mark_order_rejected — see services/checkout-workflow/src/checkout_workflow/activities.py).
# Kept in this same file rather than a new module since every route here
# exists only in service of /checkout/v2.
#
# No role checks in this file anymore: /checkout/v2 and its status poll
# are "any authenticated caller" (customer/guest alike), and the
# /internal/checkout-workflow/* routes are admin-only (checkout-workflow's
# own internal token) -- both enforced ahead of this app entirely by
# orders-gate (nginx, auth_request) + orders-verify (OPA-backed,
# policies/orders.rego). See nginx/internal-gate/orders.conf's
# $orders_auth_tier map.
internal_router = APIRouter(prefix="/internal/checkout-workflow", tags=["checkout-v2-internal"])


@router.post("/checkout/v2", response_model=CheckoutV2Response, status_code=201)
async def checkout_v2(
    payload: CheckoutRequest,
    request: Request,
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
    catalog_client: Annotated[CatalogClient, Depends(get_catalog_client)],
    temporal_client: Annotated[Client | None, Depends(get_temporal_client)],
) -> CheckoutV2Response | JSONResponse:
    if temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal unavailable")

    result = await session.execute(
        select(Cart).options(selectinload(Cart.items)).where(Cart.owner_id == claims.sub)
    )
    cart = result.scalar_one_or_none()
    if cart is None or not cart.items:
        raise HTTPException(status_code=422, detail="Cart is empty")

    # Total charge amount, computed server-side from Catalog's current
    # prices — never trusted from the client — same reasoning as
    # routers/payments.py's Stripe PaymentIntent amount.
    try:
        amount = 0.0
        for item in cart.items:
            price = await catalog_client.get_product_price(str(item.product_id))
            amount += price * item.quantity
    except CatalogUnavailableError:
        return JSONResponse(status_code=503, content={"detail": "Catalog unavailable"})

    # Generated here (not by the workflow) so create_order's idempotency
    # key is stable from the very first activity attempt — see
    # checkout-workflow's activities.create_order docstring.
    order_id = uuid.uuid4()
    workflow_input = {
        "order_id": str(order_id),
        "owner_id": claims.sub,
        "contact_name": payload.contact_name,
        "contact_email": payload.contact_email,
        "contact_phone": payload.contact_phone,
        "payment_method": payload.payment_method,
        "items": [{"product_id": str(item.product_id), "quantity": item.quantity} for item in cart.items],
        "amount": amount,
    }
    workflow_id = f"checkout-{order_id}"

    settings = request.app.state.settings
    handle = await temporal_client.start_workflow(
        "CheckoutWorkflow",
        workflow_input,
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )

    # Cart is consumed once checkout has been handed off to the workflow,
    # same timing as the existing /checkout (its cart deletion also isn't
    # gated on the reservation/payment outcome — see routers/checkout.py).
    for item in list(cart.items):
        await session.delete(item)
    await session.commit()

    try:
        workflow_result = await asyncio.wait_for(handle.result(), timeout=settings.checkout_v2_wait_seconds)
    except asyncio.TimeoutError:
        # 202, not the route's default 201 — nothing has actually finished
        # yet, the caller is expected to poll GET /checkout/v2/{workflow_id}
        # (or wait on the WebSocket/Chat channel) for the final result.
        return JSONResponse(
            status_code=202,
            content=CheckoutV2Response(workflow_id=workflow_id, status="running").model_dump(),
        )
    except WorkflowFailureError:
        # CheckoutWorkflow doesn't actually raise on the compensation path
        # (it returns a "rejected" CheckoutWorkflowResult instead, see
        # workflows.py) — this only fires for a genuinely unhandled
        # workflow-level failure (e.g. reserve_stock exhausted its own
        # bounded retries before anything was reserved).
        return JSONResponse(
            status_code=502,
            content={"detail": "Checkout workflow failed", "workflow_id": workflow_id},
        )

    order = await _get_order_or_none(session, order_id)
    status = workflow_result.get("status") if isinstance(workflow_result, dict) else None
    return CheckoutV2Response(workflow_id=workflow_id, status=status or "unknown", order=order)


@router.get("/checkout/v2/{workflow_id}", response_model=CheckoutV2Response)
async def get_checkout_v2_status(
    workflow_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    temporal_client: Annotated[Client | None, Depends(get_temporal_client)],
) -> CheckoutV2Response:
    if temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal unavailable")

    handle = temporal_client.get_workflow_handle(workflow_id)
    description = await handle.describe()

    order_id = _order_id_from_workflow_id(workflow_id)
    if description.status.name != "WORKFLOW_EXECUTION_STATUS_RUNNING":
        try:
            workflow_result = await handle.result()
        except WorkflowFailureError:
            return CheckoutV2Response(workflow_id=workflow_id, status="failed")
        order = await _get_order_or_none(session, order_id) if order_id else None
        status = workflow_result.get("status") if isinstance(workflow_result, dict) else None
        return CheckoutV2Response(workflow_id=workflow_id, status=status or "unknown", order=order)

    return CheckoutV2Response(workflow_id=workflow_id, status="running")


def _order_id_from_workflow_id(workflow_id: str) -> uuid.UUID | None:
    prefix = "checkout-"
    if not workflow_id.startswith(prefix):
        return None
    try:
        return uuid.UUID(workflow_id[len(prefix) :])
    except ValueError:
        return None


async def _get_order_or_none(session: AsyncSession, order_id: uuid.UUID) -> Order | None:
    result = await session.execute(select(Order).options(selectinload(Order.items)).where(Order.id == order_id))
    return result.scalar_one_or_none()


# --- Internal endpoints, called only by checkout-workflow's Temporal
# activities (admin-role internal token, minted via
# checkout_workflow.auth.mint_internal_token). Not part of the public
# checkout contract. ---


@internal_router.post("/orders", response_model=OrderRead, status_code=201)
async def create_order_from_workflow(
    payload: WorkflowOrderCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Order:
    # Idempotent by primary key: a retried create_order activity call for
    # the same (workflow-supplied) order_id finds the order it already
    # created instead of inserting a duplicate.
    existing = await session.get(Order, payload.id, options=[selectinload(Order.items)])
    if existing is not None:
        return existing

    order = Order(
        id=payload.id,
        owner_id=payload.owner_id,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        payment_method=payload.payment_method,
    )
    order.items = [OrderItem(product_id=item.product_id, quantity=item.quantity) for item in payload.items]
    session.add(order)
    await session.commit()
    await session.refresh(order, attribute_names=["items"])
    return order


@internal_router.patch("/orders/{order_id}/status", response_model=OrderRead)
async def update_order_status_from_workflow(
    order_id: uuid.UUID,
    payload: WorkflowOrderStatusUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Order:
    order = await session.get(Order, order_id, options=[selectinload(Order.items)])
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # Unconditional set, not a guarded transition — checkout-workflow is
    # the sole writer for a /checkout/v2 order (no concurrent Kafka
    # consumer racing it the way the choreographed saga's
    # _guarded_transition has to guard against), so redelivery/retry of
    # the same target status is already a safe no-op.
    order.status = payload.status
    await session.commit()
    await session.refresh(order, attribute_names=["items"])
    return order
