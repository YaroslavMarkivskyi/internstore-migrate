"""Product write operations. Holds the create/update/delete logic that the
route handlers used to carry inline; handlers now just translate the domain
errors below into HTTP responses and own the commit (same convention as
orders/payment_service.py). Every function stages its changes in the caller's
transaction -- including the outbox event -- and leaves the commit to the
caller so the domain change and its event stay atomic.
"""

import html
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from catalog.inventory_client import InventoryClient, InventoryUnavailableError
from catalog.models import Category, Product
from catalog.object_storage_client import ObjectStorageClient
from catalog.outbox import add_outbox_event
from catalog.schemas import ProductCreate, ProductUpdate

__all__ = [
    "InventoryUnavailableError",
    "ProductNotFoundError",
    "ProductStillPublishedError",
    "ProductOutOfStockError",
    "UnknownCategoryError",
    "create_product",
    "update_product",
    "delete_product",
]


class ProductNotFoundError(Exception):
    """The product does not exist or has been soft-deleted."""


class UnknownCategoryError(Exception):
    """A referenced category_id does not resolve to a category."""


class ProductStillPublishedError(Exception):
    """Delete attempted on a product that is still published."""


class ProductOutOfStockError(Exception):
    """(Re)publish attempted on a product with no stock in any warehouse."""


_TAG_RE = re.compile(r"<[^>]+>")


def _plain_description(description: str | None) -> str | None:
    """`description` is stored as-is (rich text from the admin form's Quill
    editor, i.e. HTML). The ProductUpdated payload feeds AI Assistant's
    embedding text and the shopping agent's own replies, both of which want
    plain prose -- strip the markup here so the event carries clean text
    while Catalog's own column keeps the HTML the edit form reloads."""
    if not description:
        return description
    text = _TAG_RE.sub(" ", description)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _as_float(value: object | None) -> float | None:
    return float(value) if value is not None else None  # type: ignore[arg-type]


def _product_updated_payload(product: Product, category: Category) -> dict:
    return {
        "product_id": str(product.id),
        "name": product.name,
        "description": _plain_description(product.description),
        # STR-146: price is part of this payload so the shopping agent's
        # search_products price_min/price_max filters have something to
        # filter on (see ai-assistant's product_embeddings table).
        "price": _as_float(product.price),
        "min_temperature": _as_float(product.min_temperature),
        "max_temperature": _as_float(product.max_temperature),
        "category_name": category.name,
    }


async def create_product(session: AsyncSession, payload: ProductCreate) -> Product:
    category = await session.get(Category, payload.category_id)
    if category is None:
        raise UnknownCategoryError

    product = Product(
        name=payload.name,
        price=payload.price,
        category_id=payload.category_id,
        description=payload.description,
        min_temperature=payload.min_temperature,
        max_temperature=payload.max_temperature,
    )
    session.add(product)
    await session.flush()

    # Embed the product straight away instead of waiting for the first PATCH
    # -- same ProductUpdated payload AI Assistant's catalog-events consumer
    # already upserts a product_embeddings row from. Products are created
    # published and search_products applies no publish filter, so there is
    # no draft-leakage concern here.
    add_outbox_event(session, "ProductUpdated", _product_updated_payload(product, category))
    return product


async def update_product(
    session: AsyncSession,
    product_id: uuid.UUID,
    payload: ProductUpdate,
    inventory_client: InventoryClient,
    internal_token: str,
) -> Product:
    product = await session.get(Product, product_id)
    if product is None or product.is_deleted:
        raise ProductNotFoundError

    updates = payload.model_dump(exclude_unset=True)

    if "category_id" in updates:
        category = await session.get(Category, updates["category_id"])
        if category is None:
            raise UnknownCategoryError

    if updates.get("is_published") is True and not product.is_published:
        # Mirrors the symmetric rule Inventory enforces the other way (see
        # stock_sync.unpublish_if_out_of_stock): a product with zero quantity
        # across every stock should not be orderable, so it should not be
        # (re)publishable either. catalog-gate already verified this
        # request's token; forwarded as-is rather than minting a new one
        # since the call is on behalf of that same authenticated request.
        # InventoryUnavailableError propagates to the handler (-> 503).
        quantity = await inventory_client.get_total_quantity(str(product_id), internal_token)
        if quantity <= 0:
            raise ProductOutOfStockError

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
                "min_temperature": _as_float(product.min_temperature),
                "max_temperature": _as_float(product.max_temperature),
            },
        )

    if updates:
        # Any PATCH that touches a field re-embeds the product (name/
        # description/category also feed the RAG text) -- fires even if a
        # field is resent unchanged, so seed-embeddings.sh can trigger an
        # initial embed for every existing product.
        category = await session.get(Category, product.category_id)
        add_outbox_event(session, "ProductUpdated", _product_updated_payload(product, category))

    return product


async def delete_product(
    session: AsyncSession,
    product_id: uuid.UUID,
    object_storage_client: ObjectStorageClient,
) -> None:
    result = await session.execute(
        select(Product).options(selectinload(Product.images)).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if product is None or product.is_deleted:
        raise ProductNotFoundError
    # Mirrors the Admin Products UI's own guard (only unpublished products
    # are deletable) -- enforced here too since the API is reachable
    # directly, not only through that UI.
    if product.is_published:
        raise ProductStillPublishedError

    # Soft delete: the row stays (is_deleted flips instead of session.delete)
    # because Inventory joins stock_items against this table client-side and
    # a hard delete left it with orphaned rows it could never clear. Orders'
    # historical pricing also still needs GET /products/{id} to resolve.
    # Images are still actually removed (DB rows + blobs) -- no reason to
    # keep serving those for a delisted product.
    for image in product.images:
        await object_storage_client.delete_object(image.object_key)
        await session.delete(image)

    product.is_deleted = True
    # STR-148: without this, AI Assistant's product_embeddings row never gets
    # cleaned up (it only reacts to ProductUpdated) and search_products keeps
    # surfacing a product_id Catalog no longer has.
    add_outbox_event(session, "ProductDeleted", {"product_id": str(product.id)})
