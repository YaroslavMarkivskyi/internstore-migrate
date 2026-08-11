import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from catalog.auth import InternalClaims, get_internal_claims, require_admin
from catalog.authz import AuthzClient, get_authz_client
from catalog.db import get_session
from catalog.inventory_client import InventoryClient, InventoryUnavailableError, get_inventory_client
from catalog.minio_client import MinioClient
from catalog.minio_dep import get_minio_client
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


@router.post("", response_model=ProductRead, status_code=201)
async def create_product(
    payload: ProductCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    authz: Annotated[AuthzClient, Depends(get_authz_client)],
) -> Product:
    # STR-140: OPA replaces this call site's previous require_admin
    # dependency (see policies/catalog.rego) -- product creation is still
    # admin-only, just decided by the sidecar now.
    if not await authz.check(
        subject={"role": claims.role, "sub": claims.sub},
        action="create",
        resource={"type": "product"},
    ):
        raise HTTPException(status_code=403, detail="Not authorized to create products")

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


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    inventory_client: Annotated[InventoryClient, Depends(get_inventory_client)],
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
    authz: Annotated[AuthzClient, Depends(get_authz_client)],
    x_internal_token: Annotated[str | None, Header()] = None,
) -> Product:
    # STR-140: OPA replaces this call site's previous require_admin
    # dependency (see policies/catalog.rego) -- product updates are still
    # admin-only, just decided by the sidecar now.
    if not await authz.check(
        subject={"role": claims.role, "sub": claims.sub},
        action="update",
        resource={"type": "product"},
    ):
        raise HTTPException(status_code=403, detail="Not authorized to update products")

    product = await session.get(Product, product_id)
    if product is None or product.is_deleted:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = payload.model_dump(exclude_unset=True)

    if "category_id" in updates:
        category = await session.get(Category, updates["category_id"])
        if category is None:
            raise HTTPException(status_code=422, detail="Unknown category_id")

    if updates.get("is_published") is True and not product.is_published:
        # Mirrors the symmetric rule Inventory enforces the other way (see
        # stock_sync.unpublish_if_out_of_stock): a product with zero
        # quantity across every stock shouldn't be orderable, so it
        # shouldn't be (re)publishable either. require_admin already
        # proved x_internal_token is valid; forwarded as-is rather than
        # minting a new one since this call is on behalf of that same
        # already-authenticated request.
        try:
            quantity = await inventory_client.get_total_quantity(str(product_id), x_internal_token or "")
        except InventoryUnavailableError as exc:
            raise HTTPException(status_code=503, detail="Inventory temporarily unavailable, please retry") from exc
        if quantity <= 0:
            raise HTTPException(status_code=422, detail="Cannot publish a product with no stock in any warehouse")

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

    if updates:
        # Keeps AI Assistant's product_embeddings table fresh: any PATCH
        # that touches a field re-embeds the product (name/description/
        # category also feed the RAG text, not just the temperature
        # thresholds above) — fires even if a field is resent unchanged, so
        # scripts/seed-embeddings.sh can trigger an initial embed for every
        # existing product without needing to know what to actually change.
        category = await session.get(Category, product.category_id)
        add_outbox_event(
            session,
            "ProductUpdated",
            {
                "product_id": str(product.id),
                "name": product.name,
                "description": product.description,
                # STR-146: price wasn't previously part of this payload —
                # added so the shopping agent's search_products filters
                # (price_min/price_max) have something to filter on (see
                # ai-assistant's product_embeddings table).
                "price": float(product.price),
                "min_temperature": float(product.min_temperature) if product.min_temperature is not None else None,
                "max_temperature": float(product.max_temperature) if product.max_temperature is not None else None,
                "category_name": category.name,
            },
        )

    await session.commit()
    await session.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_product(
    product_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    minio_client: Annotated[MinioClient, Depends(get_minio_client)],
) -> None:
    result = await session.execute(
        select(Product).options(selectinload(Product.images)).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if product is None or product.is_deleted:
        raise HTTPException(status_code=404, detail="Product not found")
    # Mirrors the Admin Products UI's own guard (ProductsMenuPopup only
    # allows deleting an unpublished product) -- enforced here too since
    # the API is reachable directly, not only through that UI.
    if product.is_published:
        raise HTTPException(status_code=409, detail="Unpublish the product before deleting it")

    # Soft delete: the row stays (is_deleted flips instead of a real
    # session.delete) because Inventory has no copy of its own of
    # product name/price -- it joins stock_items against this table
    # client-side (stockService.ts). A hard delete here used to leave
    # Inventory with orphaned stock_items rows pointing at nothing,
    # permanently 409-blocking that stock's deletion with no way for an
    # admin to even see why. Orders' historical pricing (catalog_client.py)
    # also still needs GET /products/{id} to resolve for old orders.
    # Images are still actually removed (DB rows + MinIO blobs) --
    # there's no reason to keep serving/storing those for a delisted
    # product.
    for image in product.images:
        await minio_client.delete_object(image.object_key)
        await session.delete(image)

    product.is_deleted = True
    await session.commit()
