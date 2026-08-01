from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.auth import require_admin
from catalog.db import get_session
from catalog.models import Category
from catalog.schemas import CategoryCreate, CategoryRead

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
async def list_categories(session: Annotated[AsyncSession, Depends(get_session)]) -> list[Category]:
    result = await session.execute(select(Category).order_by(Category.name))
    return list(result.scalars().all())


@router.post("", response_model=CategoryRead, status_code=201, dependencies=[Depends(require_admin)])
async def create_category(
    payload: CategoryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Category:
    existing = await session.execute(select(Category).where(Category.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Category name already exists")

    category = Category(name=payload.name)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category
