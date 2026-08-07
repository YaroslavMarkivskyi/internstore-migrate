import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from inventory.catalog_client import CatalogClient
from inventory.models import ProcessedEvent
from inventory.outbox import add_outbox_event
from inventory.reservation import consume_reservation, try_reserve
from inventory.stock_sync import unpublish_if_out_of_stock

TOPIC = "order-events"
GROUP_ID = "inventory-order-events"

# Return value is every product_id a handler's stock decrement touched --
# dispatch() checks each against Catalog (see stock_sync.py) once its
# transaction has actually committed, since unpublishing is an outbound
# HTTP side effect that has no business inside the DB transaction itself.
# Empty for handlers (e.g. OrderCreated's reservation) that only ever hold
# stock rather than decrementing it.
Handler = Callable[[AsyncSession, uuid.UUID, dict, float], Awaitable[list[uuid.UUID]]]


async def _already_processed(session: AsyncSession, event_id: uuid.UUID) -> bool:
    return await session.get(ProcessedEvent, event_id) is not None


async def handle_order_created(
    session: AsyncSession, event_id: uuid.UUID, payload: dict, ttl_seconds: float
) -> list[uuid.UUID]:
    if await _already_processed(session, event_id):
        return []
    session.add(ProcessedEvent(event_id=event_id))

    order_id = uuid.UUID(payload["order_id"])
    reservation = await try_reserve(session, order_id, payload["items"], ttl_seconds)

    if reservation is None:
        add_outbox_event(session, "StockReservationFailed", {"order_id": str(order_id)})
    else:
        add_outbox_event(session, "StockReserved", {"order_id": str(order_id)})
    return []


async def handle_payment_confirmed(
    session: AsyncSession, event_id: uuid.UUID, payload: dict, ttl_seconds: float
) -> list[uuid.UUID]:
    if await _already_processed(session, event_id):
        return []
    session.add(ProcessedEvent(event_id=event_id))

    order_id = uuid.UUID(payload["order_id"])
    result = await consume_reservation(session, order_id)
    if result is None:
        return []

    _reservation, product_ids = result
    add_outbox_event(session, "StockDecremented", {"order_id": str(order_id)})
    return product_ids


HANDLERS: dict[str, Handler] = {
    "OrderCreated": handle_order_created,
    "PaymentConfirmed": handle_payment_confirmed,
}


def make_dispatch(
    session_factory: async_sessionmaker, ttl_seconds: float, catalog_client: CatalogClient
) -> Callable[[dict], Awaitable[None]]:
    async def dispatch(envelope: dict) -> None:
        handler = HANDLERS.get(envelope.get("event_type", ""))
        if handler is None:
            return
        async with session_factory() as session:
            product_ids = await handler(
                session, uuid.UUID(envelope["event_id"]), envelope.get("payload", {}), ttl_seconds
            )
            await session.commit()

            for product_id in product_ids:
                await unpublish_if_out_of_stock(session, catalog_client, product_id)

    return dispatch
