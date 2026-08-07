import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.auth import get_internal_claims, require_authz
from inventory.catalog_client import CatalogClient, get_catalog_client
from inventory.db import get_session
from inventory.models import Reservation, ReservationItem, Stock, StockItem
from inventory.outbox import add_outbox_event
from inventory.reservation import release_reservation_by_order_id, try_reserve
from inventory.schemas import (
    AvailabilityResultItem,
    CheckAvailabilityRequest,
    CheckAvailabilityResponse,
    ReleaseStockRequest,
    ReleaseStockResponse,
    ReserveStockRequest,
    ReserveStockResponse,
    StockCreate,
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
) -> StockItem:
    await _get_stock_or_404(session, stock_id)

    existing = await session.execute(
        select(StockItem).where(
            StockItem.stock_id == stock_id,
            StockItem.product_id == payload.product_id,
        )
    )
    item = existing.scalar_one_or_none()
    if item is not None:
        item.quantity += payload.quantity
    else:
        item = StockItem(stock_id=stock_id, product_id=payload.product_id, quantity=payload.quantity)
        session.add(item)

    add_outbox_event(session, "ItemAdded", {"stock_id": str(stock_id), "product_id": str(payload.product_id)})

    await session.commit()
    await session.refresh(item)
    return item


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
) -> StockItem:
    item = await session.get(StockItem, item_id)
    if item is None or item.stock_id != stock_id:
        raise HTTPException(status_code=404, detail="Stock item not found")

    item.quantity = payload.quantity

    await session.commit()
    await session.refresh(item)

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
) -> None:
    item = await session.get(StockItem, item_id)
    if item is None or item.stock_id != stock_id:
        raise HTTPException(status_code=404, detail="Stock item not found")
    product_id = item.product_id
    # reserved_quantity is held by in-flight RESERVED reservations (see
    # StockItem's own docstring) -- removing the row out from under one
    # would leave its reservation_items pointing at nothing, so the
    # in-progress checkout/webhook flow has no item left to consume/release
    # against. Plain `quantity` (unlike delete_stock's own >0 guard) is
    # deliberately not checked here: clearing an item down to zero and
    # actually removing the row are two different admin actions, and
    # forcing "set quantity to 0 first" would just be busywork for the same
    # end state.
    if item.reserved_quantity > 0:
        raise HTTPException(status_code=409, detail="Item has quantity held by an in-progress reservation")

    # reserved_quantity == 0 means no *active* RESERVED reservation holds
    # this item, but ReservationItem rows from past RELEASED/CONSUMED
    # reservations still FK-reference it as history -- those aren't
    # in-progress holds, just an audit trail, so they don't need to block
    # this delete the way an active hold does. The FK has no ON DELETE
    # CASCADE, so they're removed explicitly here first.
    await session.execute(delete(ReservationItem).where(ReservationItem.stock_item_id == item_id))

    await session.delete(item)
    await session.commit()

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
) -> StockItem:
    await _get_stock_or_404(session, stock_id)
    await _get_stock_or_404(session, payload.to_stock_id)

    if payload.to_stock_id == stock_id:
        raise HTTPException(status_code=422, detail="Source and destination stock must differ")

    source_item = await session.get(StockItem, item_id)
    if source_item is None or source_item.stock_id != stock_id:
        raise HTTPException(status_code=404, detail="Stock item not found")
    if source_item.quantity < payload.quantity:
        raise HTTPException(status_code=422, detail="Insufficient quantity to move")

    source_item.quantity -= payload.quantity

    existing = await session.execute(
        select(StockItem).where(
            StockItem.stock_id == payload.to_stock_id,
            StockItem.product_id == source_item.product_id,
        )
    )
    dest_item = existing.scalar_one_or_none()
    if dest_item is not None:
        dest_item.quantity += payload.quantity
    else:
        dest_item = StockItem(
            stock_id=payload.to_stock_id,
            product_id=source_item.product_id,
            quantity=payload.quantity,
        )
        session.add(dest_item)

    add_outbox_event(
        session,
        "ItemAdded",
        {"stock_id": str(payload.to_stock_id), "product_id": str(source_item.product_id)},
    )

    await session.commit()
    await session.refresh(dest_item)
    return dest_item


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
# Unlike the reservation saga's Kafka path (order-events -> try_reserve, see
# consumers/order_events.py), these are plain request/response endpoints
# with no outbox event published — the Temporal-orchestrated checkout is
# deliberately choreography-free: the workflow already knows the outcome of
# every step it awaits, so there's nothing for another consumer to react to
# here, and publishing inventory-events from this path would risk the
# Kafka-based saga's own consumer (handle_stock_reserved et al.) also
# reacting to an order it was never involved in.
@router.post(
    "/reserve",
    response_model=ReserveStockResponse,
    dependencies=[Depends(get_internal_claims)],
)
async def reserve_stock(
    payload: ReserveStockRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReserveStockResponse:
    # Idempotent by order_id: Reservation.order_id is unique (see
    # models.py), so a retried reserve_stock activity call for the same
    # order_id finds the reservation it already made instead of trying
    # (and failing, or worse, double-reserving) again.
    existing = await session.execute(
        select(Reservation).where(Reservation.order_id == payload.order_id)
    )
    if existing.scalar_one_or_none() is not None:
        return ReserveStockResponse(order_id=payload.order_id, status="reserved")

    settings = request.app.state.settings
    reservation = await try_reserve(
        session,
        payload.order_id,
        [item.model_dump() for item in payload.items],
        settings.reservation_ttl_seconds,
    )
    if reservation is None:
        await session.rollback()
        return ReserveStockResponse(order_id=payload.order_id, status="insufficient_stock")

    await session.commit()
    return ReserveStockResponse(order_id=payload.order_id, status="reserved")


@router.post(
    "/release",
    response_model=ReleaseStockResponse,
    dependencies=[Depends(get_internal_claims)],
)
async def release_stock(
    payload: ReleaseStockRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReleaseStockResponse:
    # Idempotent by order_id: release_reservation_by_order_id only acts on a
    # still-RESERVED reservation and is a no-op (returns None) otherwise —
    # safe for checkout-workflow's compensation step to retry unboundedly.
    reservation = await release_reservation_by_order_id(session, payload.order_id)
    if reservation is None:
        await session.rollback()
        return ReleaseStockResponse(order_id=payload.order_id, status="not_found")

    await session.commit()
    return ReleaseStockResponse(order_id=payload.order_id, status="released")
