import uuid

from sqlalchemy import select

from telemetry.models import OutboxEvent, Store, StoreProductThreshold


async def test_create_measurement_no_auth_required(client):
    store_id = str(uuid.uuid4())
    resp = await client.post("/measurements", json={"store_id": store_id, "temperature": 5.5, "humidity": 40})
    assert resp.status_code == 201
    body = resp.json()
    assert body["store_id"] == store_id
    assert body["temperature"] == 5.5
    assert body["humidity"] == 40


async def test_create_measurement_lazily_creates_store(client):
    store_id = uuid.uuid4()
    resp = await client.post("/measurements", json={"store_id": str(store_id), "temperature": 5.5})
    assert resp.status_code == 201

    async with client.app.state.session_factory() as session:
        store = await session.get(Store, store_id)

    assert store is not None
    assert store.name == str(store_id)


async def test_create_measurement_reuses_existing_store(client):
    store_id = str(uuid.uuid4())
    await client.post("/measurements", json={"store_id": store_id, "temperature": 5.5})
    await client.post("/measurements", json={"store_id": store_id, "temperature": 6.0})

    async with client.app.state.session_factory() as session:
        stores = (await session.execute(select(Store))).scalars().all()

    assert len(stores) == 1


async def test_create_measurement_stages_no_event_when_store_tracks_no_products(client):
    store_id = str(uuid.uuid4())
    await client.post("/measurements", json={"store_id": store_id, "temperature": 5.5})

    async with client.app.state.session_factory() as session:
        events = (await session.execute(select(OutboxEvent))).scalars().all()

    assert events == []


async def test_create_measurement_stages_temperature_recorded_per_tracked_product(client):
    store_id = uuid.uuid4()
    product_a, product_b = uuid.uuid4(), uuid.uuid4()

    async with client.app.state.session_factory() as session:
        session.add(Store(id=store_id, name=str(store_id)))
        session.add(StoreProductThreshold(store_id=store_id, product_id=product_a, max_temp=5.0))
        session.add(StoreProductThreshold(store_id=store_id, product_id=product_b, max_temp=None))
        await session.commit()

    resp = await client.post("/measurements", json={"store_id": str(store_id), "temperature": 6.5, "humidity": 40})
    assert resp.status_code == 201

    async with client.app.state.session_factory() as session:
        events = (await session.execute(select(OutboxEvent))).scalars().all()

    assert len(events) == 2
    assert {e.event_type for e in events} == {"TemperatureRecorded"}
    product_ids = {e.payload["product_id"] for e in events}
    assert product_ids == {str(product_a), str(product_b)}
    for event in events:
        assert event.payload["store_id"] == str(store_id)
        assert event.payload["temperature"] == 6.5
        assert event.payload["humidity"] == 40
        assert "recorded_at" in event.payload
