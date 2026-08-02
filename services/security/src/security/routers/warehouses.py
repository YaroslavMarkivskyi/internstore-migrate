import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from security.auth import require_admin
from security.db import get_session
from security.models import Warehouse
from security.schemas import WarehouseRead, WarehouseUpdate

router = APIRouter(prefix="/warehouses", tags=["warehouses"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[WarehouseRead])
async def list_warehouses(session: Annotated[AsyncSession, Depends(get_session)]) -> list[Warehouse]:
    result = await session.execute(select(Warehouse).order_by(Warehouse.name))
    return list(result.scalars().all())


@router.patch("/{warehouse_id}", response_model=WarehouseRead)
async def update_warehouse(
    warehouse_id: uuid.UUID,
    payload: WarehouseUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Warehouse:
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    warehouse.name = payload.name
    await session.commit()
    await session.refresh(warehouse)
    return warehouse
