import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from telemetry.consumers.catalog_events import handle_product_threshold_updated
from telemetry.models import Store, StoreProductThreshold


@pytest.fixture
async def session(client) -> AsyncSession:
    async with client.app.state.session_factory() as session:
        yield session


async def test_product_threshold_updated_updates_existing_rows(session):
    store_id = uuid.uuid4()
    product_id = uuid.uuid4()
    session.add(Store(id=store_id, name=str(store_id)))
    session.add(StoreProductThreshold(store_id=store_id, product_id=product_id, max_temp=None))
    await session.flush()

    payload = {"product_id": str(product_id), "min_temperature": 2.0, "max_temperature": 8.0}
    await handle_product_threshold_updated(session, uuid.uuid4(), payload)
    await session.commit()

    threshold = await session.get(StoreProductThreshold, (store_id, product_id))
    assert threshold.max_temp == 8.0


async def test_product_threshold_updated_does_not_create_new_rows(session):
    product_id = uuid.uuid4()  # no store_product_thresholds row exists for it
    payload = {"product_id": str(product_id), "max_temperature": 8.0}

    await handle_product_threshold_updated(session, uuid.uuid4(), payload)
    await session.commit()

    threshold = await session.get(StoreProductThreshold, (uuid.uuid4(), product_id))
    assert threshold is None


async def test_product_threshold_updated_idempotent_on_redelivery(session):
    store_id = uuid.uuid4()
    product_id = uuid.uuid4()
    session.add(Store(id=store_id, name=str(store_id)))
    session.add(StoreProductThreshold(store_id=store_id, product_id=product_id, max_temp=8.0))
    await session.flush()

    event_id = uuid.uuid4()
    await handle_product_threshold_updated(session, event_id, {"product_id": str(product_id), "max_temperature": 12.0})
    await session.commit()

    threshold = await session.get(StoreProductThreshold, (store_id, product_id))
    threshold.max_temp = 5.0  # simulate a manual override after the first apply
    await session.commit()

    await handle_product_threshold_updated(session, event_id, {"product_id": str(product_id), "max_temperature": 12.0})
    await session.commit()

    threshold = await session.get(StoreProductThreshold, (store_id, product_id))
    assert threshold.max_temp == 5.0  # redelivery of the same event_id was a no-op
