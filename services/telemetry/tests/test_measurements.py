import uuid

from sqlalchemy import select

from telemetry.models import Store


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
