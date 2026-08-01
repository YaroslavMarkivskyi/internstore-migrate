import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orders.models import Order, OrderStatus

TOPIC = "inventory-events"
GROUP_ID = "orders-inventory-events"

Handler = Callable[[AsyncSession, dict], Awaitable[None]]


async def _guarded_transition(session: AsyncSession, order_id: str, from_status: OrderStatus, to_status: OrderStatus) -> None:
    # WHERE status = from_status makes this idempotent under redelivery: a
    # duplicate StockReserved/StockReservationFailed/ReservationExpired for
    # an order that has already moved on is a no-op rather than a double
    # transition.
    await session.execute(
        update(Order).where(Order.id == uuid.UUID(order_id), Order.status == from_status).values(status=to_status)
    )


async def handle_stock_reserved(session: AsyncSession, payload: dict) -> None:
    await _guarded_transition(session, payload["order_id"], OrderStatus.NEW, OrderStatus.PENDING)


async def handle_stock_reservation_failed(session: AsyncSession, payload: dict) -> None:
    await _guarded_transition(session, payload["order_id"], OrderStatus.NEW, OrderStatus.REJECTED)


async def handle_reservation_expired(session: AsyncSession, payload: dict) -> None:
    await _guarded_transition(session, payload["order_id"], OrderStatus.PENDING, OrderStatus.CANCELLED)


HANDLERS: dict[str, Handler] = {
    "StockReserved": handle_stock_reserved,
    "StockReservationFailed": handle_stock_reservation_failed,
    "ReservationExpired": handle_reservation_expired,
}


def make_dispatch(session_factory: async_sessionmaker) -> Callable[[dict], Awaitable[None]]:
    async def dispatch(envelope: dict) -> None:
        handler = HANDLERS.get(envelope.get("event_type", ""))
        if handler is None:
            return
        async with session_factory() as session:
            await handler(session, envelope.get("payload", {}))
            await session.commit()

    return dispatch
