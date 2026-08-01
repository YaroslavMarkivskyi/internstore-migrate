import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.consumers.telemetry_events import handle_temperature_threshold_violated
from inventory.models import Stock, StockItem


@pytest.fixture
async def session(client) -> AsyncSession:
    async with client.app.state.session_factory() as session:
        yield session


async def _make_stock_item(session: AsyncSession, product_id: uuid.UUID) -> StockItem:
    stock = Stock(name=f"Warehouse {uuid.uuid4()}")
    session.add(stock)
    await session.flush()
    item = StockItem(stock_id=stock.id, product_id=product_id, quantity=5)
    session.add(item)
    await session.flush()
    return item


async def test_temperature_threshold_violated_marks_item_unavailable(session):
    product_id = uuid.uuid4()
    item = await _make_stock_item(session, product_id)
    payload = {"stock_id": str(item.stock_id), "product_id": str(product_id)}

    await handle_temperature_threshold_violated(session, uuid.uuid4(), payload)
    await session.commit()

    await session.refresh(item)
    assert item.is_unavailable is True


async def test_temperature_threshold_violated_idempotent_on_redelivery(session):
    product_id = uuid.uuid4()
    item = await _make_stock_item(session, product_id)
    event_id = uuid.uuid4()
    payload = {"stock_id": str(item.stock_id), "product_id": str(product_id)}

    await handle_temperature_threshold_violated(session, event_id, payload)
    await session.commit()
    item.is_unavailable = False  # simulate admin clearing it manually
    await session.commit()

    await handle_temperature_threshold_violated(session, event_id, payload)
    await session.commit()

    await session.refresh(item)
    assert item.is_unavailable is False  # redelivery of the same event_id is a no-op


async def test_temperature_threshold_violated_unknown_stock_item_is_noop(session):
    payload = {"stock_id": str(uuid.uuid4()), "product_id": str(uuid.uuid4())}

    await handle_temperature_threshold_violated(session, uuid.uuid4(), payload)
    await session.commit()  # does not raise
