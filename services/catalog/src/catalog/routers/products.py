import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog import products_service
from catalog.db import get_session
from catalog.inventory_client import InventoryClient, InventoryUnavailableError, get_inventory_client
from catalog.object_storage_client import ObjectStorageClient
from catalog.object_storage_dep import get_object_storage_client
from catalog.models import Product
from catalog.schemas import ProductCreate, ProductRead, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])

# No role checks in this router: POST/PATCH/DELETE (admin-only) is enforced
# ahead of this app entirely -- catalog-gate (nginx, auth_request) +
# internal-gate (OPA-backed, policies/catalog.rego) reject a non-admin
# request before it ever reaches here. See docker-compose.yml's
# catalog-gate/catalog-verify. GET stays unauthenticated (public).

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[ProductRead])
async def list_products(
    session: SessionDep,
    # Opt-in pagination: omitted -> the full list, unchanged, because the
    # admin/storefront UIs still fetch everything and page client-side.
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Product]:
    stmt = select(Product).order_by(Product.name).offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: uuid.UUID, session: SessionDep) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=ProductRead, status_code=201)
async def create_product(payload: ProductCreate, session: SessionDep) -> Product:
    try:
        product = await products_service.create_product(session, payload)
    except products_service.UnknownCategoryError:
        raise HTTPException(status_code=422, detail="Unknown category_id") from None
    await session.commit()
    await session.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    session: SessionDep,
    inventory_client: Annotated[InventoryClient, Depends(get_inventory_client)],
    x_internal_token: Annotated[str | None, Header()] = None,
) -> Product:
    try:
        product = await products_service.update_product(
            session, product_id, payload, inventory_client, x_internal_token or ""
        )
    except products_service.ProductNotFoundError:
        raise HTTPException(status_code=404, detail="Product not found") from None
    except products_service.UnknownCategoryError:
        raise HTTPException(status_code=422, detail="Unknown category_id") from None
    except products_service.ProductOutOfStockError:
        raise HTTPException(
            status_code=422, detail="Cannot publish a product with no stock in any warehouse"
        ) from None
    except InventoryUnavailableError as exc:
        raise HTTPException(
            status_code=503, detail="Inventory temporarily unavailable, please retry"
        ) from exc
    await session.commit()
    await session.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID,
    session: SessionDep,
    object_storage_client: Annotated[ObjectStorageClient, Depends(get_object_storage_client)],
) -> None:
    try:
        await products_service.delete_product(session, product_id, object_storage_client)
    except products_service.ProductNotFoundError:
        raise HTTPException(status_code=404, detail="Product not found") from None
    except products_service.ProductStillPublishedError:
        raise HTTPException(status_code=409, detail="Unpublish the product before deleting it") from None
    await session.commit()
