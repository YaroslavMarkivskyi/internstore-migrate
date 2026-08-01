import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orders.models import Order, OrderStatus
from orders.outbox import add_outbox_event

TOPIC = "inventory-events"
GROUP_ID = "orders-inventory-events"

Handler = Callable[[AsyncSession, dict], Awaitable[None]]


async def _guarded_transition(
    session: AsyncSession, order_id: str, from_status: OrderStatus, to_status: OrderStatus
) -> tuple[str, str] | None:
    # WHERE status = from_status makes this idempotent under redelivery: a
    # duplicate StockReserved/StockReservationFailed/ReservationExpired for
    # an order that has already moved on is a no-op rather than a double
    # transition. RETURNING makes "did the guard actually match" atomic
    # with the update itself, and hands back the contact info callers need
    # to publish a notification event — only when a row comes back did a
    # real transition happen.
    result = await session.execute(
        update(Order)
        .where(Order.id == uuid.UUID(order_id), Order.status == from_status)
        .values(status=to_status)
        .returning(Order.contact_email, Order.contact_name)
    )
    row = result.first()
    return (row.contact_email, row.contact_name) if row is not None else None


async def handle_stock_reserved(session: AsyncSession, payload: dict) -> None:
    # No notification needed for Pending — Notifications only cares about
    # payment confirmation and rejection/cancellation.
    await _guarded_transition(session, payload["order_id"], OrderStatus.NEW, OrderStatus.PENDING)


async def handle_stock_reservation_failed(session: AsyncSession, payload: dict) -> None:
    contact = await _guarded_transition(session, payload["order_id"], OrderStatus.NEW, OrderStatus.REJECTED)
    if contact is not None:
        contact_email, contact_name = contact
        add_outbox_event(
            session,
            "OrderRejected",
            {"order_id": payload["order_id"], "contact_email": contact_email, "contact_name": contact_name},
        )


async def handle_reservation_expired(session: AsyncSession, payload: dict) -> None:
    contact = await _guarded_transition(session, payload["order_id"], OrderStatus.PENDING, OrderStatus.CANCELLED)
    if contact is not None:
        contact_email, contact_name = contact
        add_outbox_event(
            session,
            "OrderCancelled",
            {"order_id": payload["order_id"], "contact_email": contact_email, "contact_name": contact_name},
        )


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
