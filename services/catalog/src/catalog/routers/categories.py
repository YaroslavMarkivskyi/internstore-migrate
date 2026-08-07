import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.auth import InternalClaims, get_internal_claims, require_admin
from catalog.authz import AuthzClient, get_authz_client
from catalog.db import get_session
from catalog.models import Category, Product
from catalog.schemas import CategoryCreate, CategoryDeleteOptions, CategoryRead, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])

# Products moved here by the "unpublish_and_delete" deletion mode -- kept
# instead of hard-deleted so they're recoverable (just republish + move)
# rather than losing their order/stock history.
UNCATEGORIZED_CATEGORY_NAME = "Uncategorized"


async def _get_or_create_uncategorized(session: AsyncSession) -> Category:
    existing = await session.execute(select(Category).where(Category.name == UNCATEGORIZED_CATEGORY_NAME))
    category = existing.scalar_one_or_none()
    if category is None:
        category = Category(name=UNCATEGORIZED_CATEGORY_NAME)
        session.add(category)
        await session.flush()
    return category


@router.get("", response_model=list[CategoryRead])
async def list_categories(session: Annotated[AsyncSession, Depends(get_session)]) -> list[Category]:
    result = await session.execute(select(Category).order_by(Category.name))
    return list(result.scalars().all())


@router.post("", response_model=CategoryRead, status_code=201)
async def create_category(
    payload: CategoryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    authz: Annotated[AuthzClient, Depends(get_authz_client)],
) -> Category:
    # STR-140: OPA replaces this call site's previous require_admin
    # dependency (see policies/catalog.rego) -- category creation is still
    # admin-only, just decided by the sidecar now instead of an inline
    # role check.
    if not await authz.check(
        subject={"role": claims.role, "sub": claims.sub},
        action="create",
        resource={"type": "category"},
    ):
        raise HTTPException(status_code=403, detail="Not authorized to create categories")

    existing = await session.execute(select(Category).where(Category.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Category name already exists")

    category = Category(name=payload.name)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryRead, dependencies=[Depends(require_admin)])
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Category:
    category = await session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    existing = await session.execute(
        select(Category).where(Category.name == payload.name, Category.id != category_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Category name already exists")

    category.name = payload.name
    await session.commit()
    await session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_category(
    category_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    options: Annotated[CategoryDeleteOptions | None, Body()] = None,
) -> None:
    category = await session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    result = await session.execute(select(Product).where(Product.category_id == category_id))
    products = list(result.scalars().all())

    if products:
        mode = options.deletion_mode if options else None

        if mode == "move":
            if options is None or options.target_category_id is None:
                raise HTTPException(status_code=422, detail="target_category_id is required to move products")
            if options.target_category_id == category_id:
                raise HTTPException(
                    status_code=422, detail="target_category_id must differ from the category being deleted"
                )
            target_category = await session.get(Category, options.target_category_id)
            if target_category is None:
                raise HTTPException(status_code=422, detail="Unknown target_category_id")
            # Assigning the relationship (not just category_id) also
            # removes `product` from `category.products` in memory --
            # without that, the ORM still considers it a child of the
            # category being deleted and nulls its FK during the same
            # flush, clobbering this reassignment.
            for product in products:
                product.category = target_category
        elif mode == "unpublish_and_delete":
            # Products are moved to "Uncategorized" and unpublished, not
            # hard-deleted -- they stay recoverable (republish + move) and
            # this also sidesteps category_id being NOT NULL with no cascade.
            uncategorized = await _get_or_create_uncategorized(session)
            for product in products:
                product.category = uncategorized
                product.is_published = False
        else:
            # Matches the frontend's ProtectedError detection in
            # useCategories.ts, which shows a friendly "move or delete
            # products first" toast for this message.
            raise HTTPException(
                status_code=409,
                detail="Category is referenced through products; specify a deletion mode to move or delete them first",
            )

    await session.delete(category)
    await session.commit()
