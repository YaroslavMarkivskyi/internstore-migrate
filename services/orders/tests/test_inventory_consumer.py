import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orders.consumers.inventory_events import (
    handle_reservation_expired,
    handle_stock_reservation_failed,
    handle_stock_reserved,
)
from orders.models import Order, OrderStatus, OutboxEvent


@pytest.fixture
async def session(client) -> AsyncSession:
    async with client.app.state.session_factory() as session:
        yield session


async def _make_order(session: AsyncSession, status: OrderStatus) -> Order:
    order = Order(
        owner_id="customer-1",
        status=status,
        contact_name="Jane Doe",
        contact_email="jane@example.com",
        payment_method="card",
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def test_stock_reserved_transitions_new_to_pending(session):
    order = await _make_order(session, OrderStatus.NEW)

    await handle_stock_reserved(session, {"order_id": str(order.id)})
    await session.commit()

    await session.refresh(order)
    assert order.status == OrderStatus.PENDING


async def test_stock_reserved_is_a_no_op_on_redelivery(session):
    order = await _make_order(session, OrderStatus.NEW)
    await handle_stock_reserved(session, {"order_id": str(order.id)})
    await session.commit()

    # Simulate the order having since moved on (e.g. already paid) before a
    # duplicate StockReserved is redelivered.
    order.status = OrderStatus.PAID
    await session.commit()

    await handle_stock_reserved(session, {"order_id": str(order.id)})
    await session.commit()

    await session.refresh(order)
    assert order.status == OrderStatus.PAID  # unchanged, not reverted to pending


async def test_stock_reservation_failed_transitions_new_to_rejected(session):
    order = await _make_order(session, OrderStatus.NEW)

    await handle_stock_reservation_failed(session, {"order_id": str(order.id)})
    await session.commit()

    await session.refresh(order)
    assert order.status == OrderStatus.REJECTED

    result = await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "OrderRejected"))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].payload == {
        "order_id": str(order.id),
        "contact_email": "jane@example.com",
        "contact_name": "Jane Doe",
    }


async def test_stock_reservation_failed_is_a_no_op_on_redelivery_stages_no_outbox_event(session):
    order = await _make_order(session, OrderStatus.PAID)  # already moved on

    await handle_stock_reservation_failed(session, {"order_id": str(order.id)})
    await session.commit()

    result = await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "OrderRejected"))
    assert result.scalars().all() == []


async def test_reservation_expired_transitions_pending_to_cancelled(session):
    order = await _make_order(session, OrderStatus.PENDING)

    await handle_reservation_expired(session, {"order_id": str(order.id)})
    await session.commit()

    await session.refresh(order)
    assert order.status == OrderStatus.CANCELLED

    result = await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "OrderCancelled"))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].payload == {
        "order_id": str(order.id),
        "contact_email": "jane@example.com",
        "contact_name": "Jane Doe",
    }


async def test_reservation_expired_is_a_no_op_when_already_paid(session):
    order = await _make_order(session, OrderStatus.PAID)

    await handle_reservation_expired(session, {"order_id": str(order.id)})
    await session.commit()

    await session.refresh(order)
    assert order.status == OrderStatus.PAID

    result = await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "OrderCancelled"))
    assert result.scalars().all() == []


async def test_handlers_ignore_unknown_order_id(session):
    # Should not raise even if the order doesn't exist (e.g. deleted, or a
    # different environment's event leaking in).
    await handle_stock_reserved(session, {"order_id": str(uuid.uuid4())})
    await session.commit()
