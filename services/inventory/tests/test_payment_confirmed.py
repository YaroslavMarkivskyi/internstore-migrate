import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.consumers.order_events import handle_order_created, handle_payment_confirmed
from inventory.models import OutboxEvent, Stock, StockItem

TTL_SECONDS = 3600


@pytest.fixture
async def session(client) -> AsyncSession:
    async with client.app.state.session_factory() as session:
        yield session


async def _make_stock_item(session: AsyncSession, quantity: int, product_id: uuid.UUID) -> StockItem:
    stock = Stock(name=f"Warehouse {uuid.uuid4()}")
    session.add(stock)
    await session.flush()
    item = StockItem(stock_id=stock.id, product_id=product_id, quantity=quantity)
    session.add(item)
    await session.flush()
    return item


async def _reserve(session: AsyncSession, order_id: uuid.UUID, product_id: uuid.UUID, quantity: int) -> None:
    payload = {"order_id": str(order_id), "items": [{"product_id": str(product_id), "quantity": quantity}]}
    await handle_order_created(session, uuid.uuid4(), payload, TTL_SECONDS)
    await session.commit()


async def test_payment_confirmed_decrements_quantity_and_publishes_stock_decremented(session):
    product_id = uuid.uuid4()
    item = await _make_stock_item(session, quantity=10, product_id=product_id)
    order_id = uuid.uuid4()
    await _reserve(session, order_id, product_id, 4)

    await handle_payment_confirmed(session, uuid.uuid4(), {"order_id": str(order_id)}, TTL_SECONDS)
    await session.commit()

    await session.refresh(item)
    assert item.reserved_quantity == 0
    assert item.quantity == 6

    outbox = (await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "StockDecremented"))).scalars().all()
    assert len(outbox) == 1
    assert outbox[0].payload["order_id"] == str(order_id)


async def test_duplicate_payment_confirmed_same_event_id_decrements_only_once(session):
    product_id = uuid.uuid4()
    item = await _make_stock_item(session, quantity=10, product_id=product_id)
    order_id = uuid.uuid4()
    await _reserve(session, order_id, product_id, 4)

    event_id = uuid.uuid4()
    await handle_payment_confirmed(session, event_id, {"order_id": str(order_id)}, TTL_SECONDS)
    await session.commit()
    await handle_payment_confirmed(session, event_id, {"order_id": str(order_id)}, TTL_SECONDS)
    await session.commit()

    await session.refresh(item)
    assert item.quantity == 6  # not 2 — the redelivery was a no-op

    outbox = (await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "StockDecremented"))).scalars().all()
    assert len(outbox) == 1


async def test_payment_confirmed_for_unknown_order_is_a_no_op(session):
    await handle_payment_confirmed(session, uuid.uuid4(), {"order_id": str(uuid.uuid4())}, TTL_SECONDS)
    await session.commit()

    outbox = (await session.execute(select(OutboxEvent))).scalars().all()
    assert outbox == []
