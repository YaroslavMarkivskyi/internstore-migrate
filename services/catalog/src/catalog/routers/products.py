import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.auth import require_admin
from catalog.db import get_session
from catalog.models import Category, Product
from catalog.outbox import add_outbox_event
from catalog.schemas import ProductCreate, ProductRead, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
async def list_products(session: Annotated[AsyncSession, Depends(get_session)]) -> list[Product]:
    result = await session.execute(select(Product).order_by(Product.name))
    return list(result.scalars().all())


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=ProductRead, status_code=201, dependencies=[Depends(require_admin)])
async def create_product(
    payload: ProductCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Product:
    category = await session.get(Category, payload.category_id)
    if category is None:
        raise HTTPException(status_code=422, detail="Unknown category_id")

    product = Product(
        name=payload.name,
        price=payload.price,
        category_id=payload.category_id,
        description=payload.description,
        min_temperature=payload.min_temperature,
        max_temperature=payload.max_temperature,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductRead, dependencies=[Depends(require_admin)])
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = payload.model_dump(exclude_unset=True)

    if "category_id" in updates:
        category = await session.get(Category, updates["category_id"])
        if category is None:
            raise HTTPException(status_code=422, detail="Unknown category_id")

    temp_fields = {"min_temperature", "max_temperature"}
    temp_changed = any(field in updates and getattr(product, field) != updates[field] for field in temp_fields)

    for field, value in updates.items():
        setattr(product, field, value)

    if temp_changed:
        add_outbox_event(
            session,
            "ProductThresholdUpdated",
            {
                "product_id": str(product.id),
                "min_temperature": float(product.min_temperature) if product.min_temperature is not None else None,
                "max_temperature": float(product.max_temperature) if product.max_temperature is not None else None,
            },
        )

    await session.commit()
    await session.refresh(product)
    return product
