import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from telemetry.consumers.inventory_events import handle_item_added
from telemetry.models import Store, StoreProductThreshold


@pytest.fixture
async def session(client) -> AsyncSession:
    async with client.app.state.session_factory() as session:
        yield session


async def test_item_added_creates_store_and_threshold_row(session):
    stock_id = uuid.uuid4()
    product_id = uuid.uuid4()
    payload = {"stock_id": str(stock_id), "product_id": str(product_id)}

    await handle_item_added(session, uuid.uuid4(), payload)
    await session.commit()

    store = await session.get(Store, stock_id)
    assert store is not None
    assert store.name == str(stock_id)

    threshold = await session.get(StoreProductThreshold, (stock_id, product_id))
    assert threshold is not None
    assert threshold.max_temp is None


async def test_item_added_does_not_overwrite_existing_max_temp(session):
    stock_id = uuid.uuid4()
    product_id = uuid.uuid4()
    session.add(Store(id=stock_id, name=str(stock_id)))
    session.add(StoreProductThreshold(store_id=stock_id, product_id=product_id, max_temp=8.0))
    await session.flush()

    payload = {"stock_id": str(stock_id), "product_id": str(product_id)}
    await handle_item_added(session, uuid.uuid4(), payload)
    await session.commit()

    threshold = await session.get(StoreProductThreshold, (stock_id, product_id))
    assert threshold.max_temp == 8.0


async def test_item_added_idempotent_on_redelivery(session):
    stock_id = uuid.uuid4()
    product_id = uuid.uuid4()
    event_id = uuid.uuid4()
    payload = {"stock_id": str(stock_id), "product_id": str(product_id)}

    await handle_item_added(session, event_id, payload)
    await session.commit()
    await handle_item_added(session, event_id, payload)  # redelivery
    await session.commit()

    stores = await session.get(Store, stock_id)
    assert stores is not None  # no crash from a duplicate insert attempt
