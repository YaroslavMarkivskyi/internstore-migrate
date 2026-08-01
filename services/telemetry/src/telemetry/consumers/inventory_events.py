import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from telemetry.models import ProcessedEvent, StoreProductThreshold
from telemetry.stores import get_or_create_store

TOPIC = "inventory-events"
GROUP_ID = "telemetry-inventory-events"

Handler = Callable[[AsyncSession, uuid.UUID, dict], Awaitable[None]]


async def _already_processed(session: AsyncSession, event_id: uuid.UUID) -> bool:
    return await session.get(ProcessedEvent, event_id) is not None


async def handle_item_added(session: AsyncSession, event_id: uuid.UUID, payload: dict) -> None:
    if await _already_processed(session, event_id):
        return
    session.add(ProcessedEvent(event_id=event_id))

    stock_id = payload.get("stock_id")
    product_id = payload.get("product_id")
    if stock_id is None or product_id is None:
        return

    store_id = uuid.UUID(stock_id)
    await get_or_create_store(session, store_id)

    threshold = await session.get(StoreProductThreshold, (store_id, uuid.UUID(product_id)))
    if threshold is None:
        # max_temp stays null until a ProductThresholdUpdated arrives for
        # this product (see catalog_events.py) — this event only registers
        # that this store now carries this product.
        session.add(StoreProductThreshold(store_id=store_id, product_id=uuid.UUID(product_id)))


HANDLERS: dict[str, Handler] = {
    "ItemAdded": handle_item_added,
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
