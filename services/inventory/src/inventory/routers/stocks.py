import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.auth import require_admin
from inventory.db import get_session
from inventory.models import Stock, StockItem
from inventory.schemas import (
    AvailabilityResultItem,
    CheckAvailabilityRequest,
    CheckAvailabilityResponse,
    StockItemCreate,
    StockItemMove,
    StockItemRead,
    StockRead,
)

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
    dependencies=[Depends(require_admin)],
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

    await session.commit()
    await session.refresh(item)
    return item


@router.post(
    "/{stock_id}/items/{item_id}/move",
    response_model=StockItemRead,
    dependencies=[Depends(require_admin)],
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

    await session.commit()
    await session.refresh(dest_item)
    return dest_item


@router.post("/check-availability", response_model=CheckAvailabilityResponse)
async def check_availability(
    payload: CheckAvailabilityRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CheckAvailabilityResponse:
    results: list[AvailabilityResultItem] = []
    for requested in payload.items:
        total = await session.execute(
            select(StockItem.quantity).where(StockItem.product_id == requested.product_id)
        )
        available = sum(total.scalars().all())
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
