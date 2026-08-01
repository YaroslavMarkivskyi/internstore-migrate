import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.consumers.order_events import handle_order_created
from inventory.models import OutboxEvent, Reservation, Stock, StockItem

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


async def test_order_created_reserves_stock_and_publishes_stock_reserved(session):
    product_id = uuid.uuid4()
    item = await _make_stock_item(session, quantity=10, product_id=product_id)
    order_id = uuid.uuid4()
    event_id = uuid.uuid4()
    payload = {"order_id": str(order_id), "items": [{"product_id": str(product_id), "quantity": 3}]}

    await handle_order_created(session, event_id, payload, TTL_SECONDS)
    await session.commit()

    await session.refresh(item)
    assert item.reserved_quantity == 3

    outbox = (await session.execute(select(OutboxEvent))).scalars().all()
    assert len(outbox) == 1
    assert outbox[0].event_type == "StockReserved"
    assert outbox[0].payload["order_id"] == str(order_id)


async def test_order_created_insufficient_stock_publishes_stock_reservation_failed(session):
    product_id = uuid.uuid4()
    await _make_stock_item(session, quantity=1, product_id=product_id)
    order_id = uuid.uuid4()
    payload = {"order_id": str(order_id), "items": [{"product_id": str(product_id), "quantity": 5}]}

    await handle_order_created(session, uuid.uuid4(), payload, TTL_SECONDS)
    await session.commit()

    reservations = (await session.execute(select(Reservation))).scalars().all()
    assert reservations == []

    outbox = (await session.execute(select(OutboxEvent))).scalars().all()
    assert len(outbox) == 1
    assert outbox[0].event_type == "StockReservationFailed"


async def test_duplicate_order_created_same_event_id_reserves_only_once(session):
    product_id = uuid.uuid4()
    item = await _make_stock_item(session, quantity=10, product_id=product_id)
    order_id = uuid.uuid4()
    event_id = uuid.uuid4()  # same event_id both times — simulates redelivery
    payload = {"order_id": str(order_id), "items": [{"product_id": str(product_id), "quantity": 3}]}

    await handle_order_created(session, event_id, payload, TTL_SECONDS)
    await session.commit()
    await handle_order_created(session, event_id, payload, TTL_SECONDS)
    await session.commit()

    await session.refresh(item)
    assert item.reserved_quantity == 3  # not 6 — the redelivery was a no-op

    outbox = (await session.execute(select(OutboxEvent))).scalars().all()
    assert len(outbox) == 1  # exactly one StockReserved published, not two
