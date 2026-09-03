import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog import categories_service
from catalog.db import get_session
from catalog.models import Category
from catalog.schemas import CategoryCreate, CategoryDeleteOptions, CategoryRead, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])

# No role checks in this router: POST/PATCH/DELETE (admin-only) is enforced
# ahead of this app entirely -- catalog-gate (nginx, auth_request) +
# internal-gate (OPA-backed, policies/catalog.rego). GET stays public.

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[CategoryRead])
async def list_categories(
    session: SessionDep,
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Category]:
    stmt = select(Category).order_by(Category.name).offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=CategoryRead, status_code=201)
async def create_category(payload: CategoryCreate, session: SessionDep) -> Category:
    try:
        category = await categories_service.create_category(session, payload.name)
    except categories_service.CategoryNameExistsError:
        raise HTTPException(status_code=409, detail="Category name already exists") from None
    await session.commit()
    await session.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryRead)
async def update_category(category_id: uuid.UUID, payload: CategoryUpdate, session: SessionDep) -> Category:
    try:
        category = await categories_service.rename_category(session, category_id, payload.name)
    except categories_service.CategoryNotFoundError:
        raise HTTPException(status_code=404, detail="Category not found") from None
    except categories_service.CategoryNameExistsError:
        raise HTTPException(status_code=409, detail="Category name already exists") from None
    await session.commit()
    await session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: uuid.UUID,
    session: SessionDep,
    options: Annotated[CategoryDeleteOptions | None, Body()] = None,
) -> None:
    try:
        await categories_service.delete_category(session, category_id, options)
    except categories_service.CategoryNotFoundError:
        raise HTTPException(status_code=404, detail="Category not found") from None
    except categories_service.InvalidMoveTargetError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    except categories_service.CategoryHasProductsError:
        # Matches the frontend's ProtectedError detection in useCategories.ts.
        raise HTTPException(
            status_code=409,
            detail="Category is referenced through products; specify a deletion mode to move or delete them first",
        ) from None
    await session.commit()
