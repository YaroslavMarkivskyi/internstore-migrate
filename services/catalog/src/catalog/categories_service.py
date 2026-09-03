"""Category write operations. Same split as products_service: handlers
translate the domain errors below into HTTP responses and own the commit;
this module stages changes in the caller's transaction.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.models import Category, Product
from catalog.schemas import CategoryDeleteOptions

# Products relocated here by "unpublish_and_delete" -- kept instead of
# hard-deleted so they stay recoverable (republish + move) rather than
# losing their order/stock history.
UNCATEGORIZED_CATEGORY_NAME = "Uncategorized"


class CategoryNotFoundError(Exception):
    """No category with that id."""


class CategoryNameExistsError(Exception):
    """Another category already uses that name."""


class CategoryHasProductsError(Exception):
    """Delete attempted on a non-empty category with no deletion mode given."""


class InvalidMoveTargetError(Exception):
    """The 'move' deletion mode was given an absent/invalid target_category_id."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


async def _name_taken(session: AsyncSession, name: str, *, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(Category).where(Category.name == name)
    if exclude_id is not None:
        stmt = stmt.where(Category.id != exclude_id)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _get_or_create_uncategorized(session: AsyncSession) -> Category:
    existing = await session.execute(select(Category).where(Category.name == UNCATEGORIZED_CATEGORY_NAME))
    category = existing.scalar_one_or_none()
    if category is None:
        category = Category(name=UNCATEGORIZED_CATEGORY_NAME)
        session.add(category)
        await session.flush()
    return category


async def create_category(session: AsyncSession, name: str) -> Category:
    if await _name_taken(session, name):
        raise CategoryNameExistsError
    category = Category(name=name)
    session.add(category)
    await session.flush()
    return category


async def rename_category(session: AsyncSession, category_id: uuid.UUID, name: str) -> Category:
    category = await session.get(Category, category_id)
    if category is None:
        raise CategoryNotFoundError
    if await _name_taken(session, name, exclude_id=category_id):
        raise CategoryNameExistsError
    category.name = name
    return category


async def delete_category(
    session: AsyncSession,
    category_id: uuid.UUID,
    options: CategoryDeleteOptions | None,
) -> None:
    category = await session.get(Category, category_id)
    if category is None:
        raise CategoryNotFoundError

    result = await session.execute(select(Product).where(Product.category_id == category_id))
    products = list(result.scalars().all())

    if products:
        mode = options.deletion_mode if options else None
        if mode == "move":
            await _move_products(session, products, category_id, options)
        elif mode == "unpublish_and_delete":
            uncategorized = await _get_or_create_uncategorized(session)
            for product in products:
                product.category = uncategorized
                product.is_published = False
        else:
            raise CategoryHasProductsError

    await session.delete(category)


async def _move_products(
    session: AsyncSession,
    products: list[Product],
    category_id: uuid.UUID,
    options: CategoryDeleteOptions | None,
) -> None:
    if options is None or options.target_category_id is None:
        raise InvalidMoveTargetError("target_category_id is required to move products")
    if options.target_category_id == category_id:
        raise InvalidMoveTargetError("target_category_id must differ from the category being deleted")
    target_category = await session.get(Category, options.target_category_id)
    if target_category is None:
        raise InvalidMoveTargetError("Unknown target_category_id")
    # Assigning the relationship (not just category_id) also removes each
    # product from category.products in memory -- without that the ORM still
    # considers it a child of the category being deleted and nulls its FK
    # during the same flush, clobbering this reassignment.
    for product in products:
        product.category = target_category
