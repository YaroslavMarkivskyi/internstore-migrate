import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory import commands, events as ev
from inventory.auth import get_internal_claims, require_authz
from inventory.catalog_client import CatalogClient, get_catalog_client
from inventory.db import get_session
from inventory.event_store import ConcurrencyConflict
from inventory.models import Stock, StockEvent, StockItem, StockSnapshot
from inventory.projector import replay
from inventory.schemas import (
    AvailabilityResultItem,
    CheckAvailabilityRequest,
    CheckAvailabilityResponse,
    ReleaseStockRequest,
    ReleaseStockResponse,
    ReserveStockRequest,
    ReserveStockResponse,
    StockCreate,
    StockEventHistoryPage,
    StockEventRead,
    StockItemAsOf,
    StockItemCreate,
    StockItemMove,
    StockItemQuantityUpdate,
    StockItemRead,
    StockRead,
    StockUpdate,
)
from inventory.stock_sync import unpublish_if_out_of_stock

router = APIRouter(prefix="/stocks", tags=["stocks"])


async def _get_stock_or_404(session: AsyncSession, stock_id: uuid.UUID) -> Stock:
    stock = await session.get(Stock, stock_id)
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock


@router.get("", response_model=list[StockRead])
async def list_stocks(session: Annotated[AsyncSession, Depends(get_session)]) -> list[Stock]:
    result = await session.execute(select(Stock).order_by(Stock.name))
    return list(result.scalars().all())


@router.post("", response_model=StockRead, status_code=201, dependencies=[Depends(require_authz("create", "stock"))])
async def create_stock(
    payload: StockCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Stock:
    existing = await session.execute(select(Stock).where(Stock.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Stock name already exists")

    stock = Stock(name=payload.name, temperature=payload.temperature, humidity=payload.humidity)
    session.add(stock)
    await session.commit()
    await session.refresh(stock)
    return stock


@router.get("/{stock_id}", response_model=StockRead)
async def get_stock(
    stock_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Stock:
    return await _get_stock_or_404(session, stock_id)


@router.patch("/{stock_id}", response_model=StockRead, dependencies=[Depends(require_authz("update", "stock"))])
async def update_stock(
    stock_id: uuid.UUID,
    payload: StockUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Stock:
    stock = await _get_stock_or_404(session, stock_id)

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        existing = await session.execute(
            select(Stock).where(Stock.name == updates["name"], Stock.id != stock_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Stock name already exists")

    for field, value in updates.items():
        setattr(stock, field, value)

    await session.commit()
    await session.refresh(stock)
    return stock


@router.delete("/{stock_id}", status_code=204, dependencies=[Depends(require_authz("delete", "stock"))])
async def delete_stock(
    stock_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    stock = await _get_stock_or_404(session, stock_id)

    has_quantity = await session.execute(
        select(StockItem).where(StockItem.stock_id == stock_id, StockItem.quantity > 0)
    )
    if has_quantity.scalars().first() is not None:
        raise HTTPException(status_code=409, detail="Stock still has items in it")

    await session.delete(stock)
    await session.commit()


@router.get("/{stock_id}/items", response_model=list[StockItemRead])
async def list_stock_items(
    stock_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[StockItem]:
    await _get_stock_or_404(session, stock_id)
    result = await session.execute(select(StockItem).where(StockItem.stock_id == stock_id))
    return list(result.scalars().all())


@router.post(
    "/{stock_id}/items",
    response_model=StockItemRead,
    status_code=201,
    dependencies=[Depends(require_authz("create", "stock_item"))],
)
async def receive_stock_item(
    stock_id: uuid.UUID,
    payload: StockItemCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
) -> StockItem:
    await _get_stock_or_404(session, stock_id)

    return await commands.receive_stock_item(request.app.state.session_factory, stock_id, payload.product_id, payload.quantity)


@router.patch(
    "/{stock_id}/items/{item_id}",
    response_model=StockItemRead,
    dependencies=[Depends(require_authz("update", "stock_item"))],
)
async def update_stock_item_quantity(
    stock_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: StockItemQuantityUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    catalog_client: Annotated[CatalogClient, Depends(get_catalog_client)],
    request: Request,
) -> StockItem:
    try:
        item = await commands.set_stock_item_quantity(request.app.state.session_factory, stock_id, item_id, payload.quantity)
    except commands.StockItemNotFound as exc:
        raise HTTPException(status_code=404, detail="Stock item not found") from exc

    await unpublish_if_out_of_stock(session, catalog_client, item.product_id)

    return item


@router.delete(
    "/{stock_id}/items/{item_id}",
    status_code=204,
    dependencies=[Depends(require_authz("delete", "stock_item"))],
)
async def delete_stock_item(
    stock_id: uuid.UUID,
    item_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    catalog_client: Annotated[CatalogClient, Depends(get_catalog_client)],
    request: Request,
) -> None:
    try:
        product_id = await commands.remove_stock_item(request.app.state.session_factory, stock_id, item_id)
    except commands.StockItemNotFound as exc:
        raise HTTPException(status_code=404, detail="Stock item not found") from exc
    except commands.ReservedQuantityHeld as exc:
        raise HTTPException(status_code=409, detail="Item has quantity held by an in-progress reservation") from exc

    await unpublish_if_out_of_stock(session, catalog_client, product_id)


@router.post(
    "/{stock_id}/items/{item_id}/move",
    response_model=StockItemRead,
    dependencies=[Depends(require_authz("move", "stock_item"))],
)
async def move_stock_item(
    stock_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: StockItemMove,
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
) -> StockItem:
    await _get_stock_or_404(session, stock_id)
    await _get_stock_or_404(session, payload.to_stock_id)

    try:
        return await commands.move_stock_item(
            request.app.state.session_factory, stock_id, item_id, payload.to_stock_id, payload.quantity
        )
    except commands.SameStockError as exc:
        raise HTTPException(status_code=422, detail="Source and destination stock must differ") from exc
    except commands.StockItemNotFound as exc:
        raise HTTPException(status_code=404, detail="Stock item not found") from exc
    except commands.InsufficientQuantity as exc:
        raise HTTPException(status_code=422, detail="Insufficient quantity to move") from exc


@router.post(
    "/{stock_id}/items/{item_id}/mark-available",
    response_model=StockItemRead,
    dependencies=[Depends(require_authz("update", "stock_item"))],
)
async def mark_stock_item_available(
    stock_id: uuid.UUID,
    item_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
) -> StockItem:
    """STR-149: the admin-facing counterpart to the telemetry-events
    consumer's automatic MarkedUnavailable -- previously nothing ever
    cleared `is_unavailable` (see the pre-STR-149 StockItem docstring); this
    is a genuinely new capability, added because the ticket's own event
    list requires a symmetric MarkedAvailable and there was no existing
    trigger to hang it off of."""
    item = await session.get(StockItem, item_id)
    if item is None or item.stock_id != stock_id:
        raise HTTPException(status_code=404, detail="Stock item not found")

    try:
        return await commands.mark_available(request.app.state.session_factory, stock_id, item.product_id)
    except commands.StockItemNotFound as exc:
        raise HTTPException(status_code=404, detail="Stock item not found") from exc


@router.post(
    "/check-availability",
    response_model=CheckAvailabilityResponse,
    dependencies=[Depends(get_internal_claims)],
)
async def check_availability(
    payload: CheckAvailabilityRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CheckAvailabilityResponse:
    results: list[AvailabilityResultItem] = []
    for requested in payload.items:
        total = await session.execute(
            select(StockItem.quantity, StockItem.reserved_quantity).where(
                StockItem.product_id == requested.product_id
            )
        )
        available = sum(quantity - reserved_quantity for quantity, reserved_quantity in total.all())
        results.append(
            AvailabilityResultItem(
                product_id=requested.product_id,
                requested=requested.quantity,
                available=available,
                sufficient=available >= requested.quantity,
            )
        )

    return CheckAvailabilityResponse(
        sufficient=all(r.sufficient for r in results),
        items=results,
    )


# STR-139: synchronous reserve/release-by-order_id, called directly by
# checkout-workflow's `reserve_stock`/`release_stock` Temporal activities.
# Unlike the reservation saga's Kafka path (order-events -> commands.
# build_reserve, see consumers/order_events.py), these are plain
# request/response endpoints with no outbox event published -- the
# Temporal-orchestrated checkout is deliberately choreography-free: the
# workflow already knows the outcome of every step it awaits, so there's
# nothing for another consumer to react to here, and publishing
# inventory-events from this path would risk the Kafka-based saga's own
# consumer (handle_stock_reserved et al.) also reacting to an order it was
# never involved in.
#
# STR-149: request/response contracts here are unchanged. What changed is
# only the internal implementation -- commands.reserve/commands.release
# append events + update the projection synchronously (with retry on
# ConcurrencyConflict) instead of directly mutating `reserved_quantity`.
# This endpoint is the one genuinely concurrency-sensitive write path
# (concurrent orders/retries for the same product can race), which is why
# it goes through the retrying `commands.reserve`/`commands.release`
# rather than the session-scoped `build_*` functions the Kafka consumers
# use directly.
@router.post(
    "/reserve",
    response_model=ReserveStockResponse,
    dependencies=[Depends(get_internal_claims)],
)
async def reserve_stock(
    payload: ReserveStockRequest,
    request: Request,
) -> ReserveStockResponse:
    settings = request.app.state.settings
    try:
        status = await commands.reserve(
            request.app.state.session_factory,
            payload.order_id,
            [item.model_dump() for item in payload.items],
            settings.reservation_ttl_seconds,
        )
    except ConcurrencyConflict as exc:
        # STR-160b: run_with_retry (commands.py) already retried
        # MAX_ATTEMPTS times against real concurrent writers for the same
        # product before giving up -- this is a genuine "someone else won
        # the race" outcome, not a server fault, so it's surfaced as a
        # handled 409 instead of an uncaught 500 (STR-159b found the
        # latter via live load testing). The detail string is what a
        # caller actually needs: this is retry-able, and order_id, so the
        # Temporal activity's own logs/retries can be correlated to it.
        raise HTTPException(
            status_code=409,
            detail=f"Reservation for order {payload.order_id} conflicted with a concurrent writer "
            "after exhausting retries -- please retry",
        ) from exc
    return ReserveStockResponse(order_id=payload.order_id, status=status)


@router.post(
    "/release",
    response_model=ReleaseStockResponse,
    dependencies=[Depends(get_internal_claims)],
)
async def release_stock(
    payload: ReleaseStockRequest,
    request: Request,
) -> ReleaseStockResponse:
    try:
        status = await commands.release(request.app.state.session_factory, payload.order_id)
    except ConcurrencyConflict as exc:
        # Same reasoning as reserve_stock above -- release_stock goes
        # through the same retrying run_with_retry mechanism and can
        # exhaust retries under the same kind of contention.
        raise HTTPException(
            status_code=409,
            detail=f"Release for order {payload.order_id} conflicted with a concurrent writer "
            "after exhausting retries -- please retry",
        ) from exc
    return ReleaseStockResponse(order_id=payload.order_id, status=status)


# STR-149: the audit-trail and time-travel payoff -- admin-only, read-only,
# additive. Both reuse `projector.apply_event`/`replay` -- the same fold
# function the live projection is built from -- so history/as-of are never
# a second implementation of what an event means.
@router.get(
    "/{stock_id}/{product_id}/history",
    response_model=StockEventHistoryPage,
    dependencies=[Depends(require_authz("read", "stock_item_history"))],
)
async def get_stock_item_history(
    stock_id: uuid.UUID,
    product_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    cursor: int = 0,
    limit: int = 50,
) -> StockEventHistoryPage:
    limit = max(1, min(limit, 200))
    aggregate_id = ev.compute_aggregate_id(stock_id, product_id)

    result = await session.execute(
        select(StockEvent)
        .where(StockEvent.aggregate_id == aggregate_id, StockEvent.sequence_number > cursor)
        .order_by(StockEvent.sequence_number)
        .limit(limit + 1)
    )
    rows = list(result.scalars().all())

    next_cursor = rows[limit - 1].sequence_number if len(rows) > limit else None
    return StockEventHistoryPage(
        items=[StockEventRead.model_validate(row) for row in rows[:limit]],
        next_cursor=next_cursor,
    )


@router.get(
    "/{stock_id}/{product_id}/as-of",
    response_model=StockItemAsOf,
    dependencies=[Depends(require_authz("read", "stock_item_history"))],
)
async def get_stock_item_as_of(
    stock_id: uuid.UUID,
    product_id: uuid.UUID,
    timestamp: datetime,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StockItemAsOf:
    aggregate_id = ev.compute_aggregate_id(stock_id, product_id)

    snapshot_result = await session.execute(
        select(StockSnapshot)
        .where(StockSnapshot.aggregate_id == aggregate_id, StockSnapshot.created_at <= timestamp)
        .order_by(StockSnapshot.sequence_number.desc())
        .limit(1)
    )
    snapshot = snapshot_result.scalar_one_or_none()

    if snapshot is not None:
        base_state = {
            "stock_id": uuid.UUID(snapshot.state["stock_id"]) if snapshot.state["stock_id"] else None,
            "product_id": uuid.UUID(snapshot.state["product_id"]) if snapshot.state["product_id"] else None,
            "quantity": snapshot.state["quantity"],
            "reserved_quantity": snapshot.state["reserved_quantity"],
            "is_unavailable": snapshot.state["is_unavailable"],
            "exists": snapshot.state["exists"],
        }
        base_sequence = snapshot.sequence_number
    else:
        base_state = None
        base_sequence = 0

    events_result = await session.execute(
        select(StockEvent)
        .where(
            StockEvent.aggregate_id == aggregate_id,
            StockEvent.sequence_number > base_sequence,
            StockEvent.created_at <= timestamp,
        )
        .order_by(StockEvent.sequence_number)
    )
    events = list(events_result.scalars().all())

    if snapshot is None and not events:
        raise HTTPException(status_code=404, detail="No stock history for this item as of the given timestamp")

    state = replay(events, base_state)
    if not state["exists"]:
        raise HTTPException(status_code=404, detail="No stock history for this item as of the given timestamp")

    return StockItemAsOf(
        stock_id=state["stock_id"],
        product_id=state["product_id"],
        quantity=state["quantity"],
        reserved_quantity=state["reserved_quantity"],
        is_unavailable=state["is_unavailable"],
        as_of=timestamp,
    )
