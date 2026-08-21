import uuid


async def test_list_stores_empty(client):
    resp = await client.get("/stores")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_stores_reflects_latest_reading(client):
    store_id = str(uuid.uuid4())
    await client.post("/measurements", json={"store_id": store_id, "temperature": 4.0})
    await client.post("/measurements", json={"store_id": store_id, "temperature": 9.0})

    resp = await client.get("/stores")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == store_id
    assert body[0]["current_temperature"] == 9.0
    assert body[0]["has_open_violation"] is False


async def test_update_store_not_found(client, admin_token):
    resp = await client.patch(
        f"/stores/{uuid.uuid4()}",
        json={"threshold_temp": 8},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 404


async def test_update_store_sets_name_and_threshold(client, admin_token):
    store_id = str(uuid.uuid4())
    await client.post("/measurements", json={"store_id": store_id, "temperature": 4.0})

    resp = await client.patch(
        f"/stores/{store_id}",
        json={"name": "Warehouse A", "threshold_temp": 8},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Warehouse A"
    assert body["threshold_temp"] == 8


async def test_list_readings_not_found(client, admin_token):
    resp = await client.get(f"/stores/{uuid.uuid4()}/readings", headers={"x-internal-token": admin_token})
    assert resp.status_code == 404


async def test_list_readings_returns_all_by_default(client, admin_token):
    store_id = str(uuid.uuid4())
    await client.post("/measurements", json={"store_id": store_id, "temperature": 4.0})
    await client.post("/measurements", json={"store_id": store_id, "temperature": 5.0})

    resp = await client.get(f"/stores/{store_id}/readings", headers={"x-internal-token": admin_token})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_delete_readings_clears_history(client, admin_token):
    store_id = str(uuid.uuid4())
    await client.post("/measurements", json={"store_id": store_id, "temperature": 4.0})

    resp = await client.delete(f"/stores/{store_id}/readings", headers={"x-internal-token": admin_token})
    assert resp.status_code == 204

    listed = await client.get(f"/stores/{store_id}/readings", headers={"x-internal-token": admin_token})
    assert listed.json() == []
