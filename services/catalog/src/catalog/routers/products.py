import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.auth import require_admin
from catalog.db import get_session
from catalog.models import Category, Product
from catalog.schemas import ProductCreate, ProductRead

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
