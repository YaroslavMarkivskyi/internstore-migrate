import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from telemetry.models import ProcessedEvent, StoreProductThreshold

TOPIC = "catalog-events"
GROUP_ID = "telemetry-catalog-events"

Handler = Callable[[AsyncSession, uuid.UUID, dict], Awaitable[None]]


async def _already_processed(session: AsyncSession, event_id: uuid.UUID) -> bool:
    return await session.get(ProcessedEvent, event_id) is not None


async def handle_product_threshold_updated(session: AsyncSession, event_id: uuid.UUID, payload: dict) -> None:
    """A product's threshold change applies to every store already tracking
    that product — it does not create new store_product_thresholds rows. A
    store only starts tracking a product once Inventory tells us via
    ItemAdded (see inventory_events.py)."""
    if await _already_processed(session, event_id):
        return
    session.add(ProcessedEvent(event_id=event_id))

    product_id = payload.get("product_id")
    if product_id is None:
        return

    result = await session.execute(
        select(StoreProductThreshold).where(StoreProductThreshold.product_id == uuid.UUID(product_id))
    )
    rows = list(result.scalars().all())
    for row in rows:
        row.max_temp = payload.get("max_temperature")


HANDLERS: dict[str, Handler] = {
    "ProductThresholdUpdated": handle_product_threshold_updated,
}


def make_dispatch(session_factory: async_sessionmaker) -> Callable[[dict], Awaitable[None]]:
    async def dispatch(envelope: dict) -> None:
        handler = HANDLERS.get(envelope.get("event_type", ""))
        if handler is None:
            return
        async with session_factory() as session:
            await handler(session, uuid.UUID(envelope["event_id"]), envelope.get("payload", {}))
            await session.commit()

    return dispatch
