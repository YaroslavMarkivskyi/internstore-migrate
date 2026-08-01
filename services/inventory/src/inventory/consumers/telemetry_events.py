import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from inventory.models import ProcessedEvent, StockItem

TOPIC = "telemetry-events"
GROUP_ID = "inventory-telemetry-events"

Handler = Callable[[AsyncSession, uuid.UUID, dict], Awaitable[None]]


async def _already_processed(session: AsyncSession, event_id: uuid.UUID) -> bool:
    return await session.get(ProcessedEvent, event_id) is not None


async def handle_temperature_threshold_violated(session: AsyncSession, event_id: uuid.UUID, payload: dict) -> None:
    if await _already_processed(session, event_id):
        return
    session.add(ProcessedEvent(event_id=event_id))

    stock_id = payload.get("stock_id")
    product_id = payload.get("product_id")
    if stock_id is None or product_id is None:
        return

    result = await session.execute(
        select(StockItem).where(
            StockItem.stock_id == uuid.UUID(stock_id),
            StockItem.product_id == uuid.UUID(product_id),
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        return

    item.is_unavailable = True


HANDLERS: dict[str, Handler] = {
    "TemperatureThresholdViolated": handle_temperature_threshold_violated,
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
