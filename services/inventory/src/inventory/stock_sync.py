import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.catalog_client import CatalogClient
from inventory.models import StockItem


async def unpublish_if_out_of_stock(
    session: AsyncSession,
    catalog_client: CatalogClient,
    product_id: uuid.UUID,
) -> None:
    """A product with zero quantity across every stock (not just the one
    that was just touched -- summed here, same as check-availability's own
    query) shouldn't stay visible/orderable on the storefront. Call this
    after any operation that can bring a product's total down to zero:
    deleting a stock item, editing its quantity down, or an order
    consuming the last unit on PaymentConfirmed. Moving a stock item
    between stocks never changes the *total*, so callers don't need this
    after a move.
    """
    result = await session.execute(
        select(func.coalesce(func.sum(StockItem.quantity), 0)).where(StockItem.product_id == product_id)
    )
    if result.scalar_one() == 0:
        await catalog_client.unpublish_product(str(product_id))
