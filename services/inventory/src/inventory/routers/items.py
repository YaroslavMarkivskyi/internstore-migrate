import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.db import get_session
from inventory.models import StockItem
from inventory.schemas import ConsolidatedItemRead

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ConsolidatedItemRead])
async def list_items(
    session: Annotated[AsyncSession, Depends(get_session)],
    stock_id: Annotated[uuid.UUID | None, Query()] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[ConsolidatedItemRead]:
    total_quantity = func.sum(StockItem.quantity).label("quantity")
    stmt = select(StockItem.product_id, total_quantity)

    if stock_id is not None:
        stmt = stmt.where(StockItem.stock_id == stock_id)

    stmt = stmt.group_by(StockItem.product_id)

    if min_quantity is not None:
        stmt = stmt.having(total_quantity >= min_quantity)
    if max_quantity is not None:
        stmt = stmt.having(total_quantity <= max_quantity)

    stmt = stmt.order_by(StockItem.product_id)

    result = await session.execute(stmt)
    return [
        ConsolidatedItemRead(product_id=product_id, quantity=quantity)
        for product_id, quantity in result.all()
    ]
