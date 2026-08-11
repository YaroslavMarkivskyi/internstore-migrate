import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from inventory import commands
from inventory.models import ProcessedEvent

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

    # STR-149: build_mark_unavailable directly against this handler's own
    # session -- same single-consumer-instance reasoning as
    # order_events.py, no retry loop needed here. Returns None (a no-op)
    # if the aggregate has never had a StockItemCreated event, mirroring
    # the pre-STR-149 "if item is None: return" behavior.
    outcome = await commands.build_mark_unavailable(
        session, uuid.UUID(stock_id), uuid.UUID(product_id), reason="temperature_threshold_violated"
    )
    if outcome is None:
        return
    appends, _result = outcome
    await commands.apply(session, appends)


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
