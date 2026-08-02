import uuid


async def _attempt(client, warehouse_id, template):
    return await client.post("/auth/fingerprint", json={"warehouse_id": warehouse_id, "fingerprint_template": template})


async def test_visit_log_requires_admin(client, customer_token):
    resp = await client.get("/visit-log", headers={"x-internal-token": customer_token})
    assert resp.status_code == 403


async def test_filter_by_warehouse_id(client, admin_headers):
    warehouse_a = str(uuid.uuid4())
    warehouse_b = str(uuid.uuid4())
    await _attempt(client, warehouse_a, "x")
    await _attempt(client, warehouse_b, "y")

    resp = await client.get("/visit-log", params={"warehouse_id": warehouse_a}, headers=admin_headers)
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["warehouse_id"] == warehouse_a


async def test_filter_by_auth_type(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    await _attempt(client, warehouse_id, "x")
    await client.post("/auth/nfc", json={"warehouse_id": warehouse_id, "card_uid": "c1"})

    resp = await client.get("/visit-log", params={"auth_type": "nfc"}, headers=admin_headers)
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["auth_type"] == "nfc"


async def test_filter_by_success(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    await client.post(
        "/users",
        json={"name": "E", "auth_type": "fingerprint", "credential": "good", "warehouse_ids": [warehouse_id]},
        headers=admin_headers,
    )
    await _attempt(client, warehouse_id, "good")
    await _attempt(client, warehouse_id, "bad")

    resp = await client.get("/visit-log", params={"success": "true"}, headers=admin_headers)
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["success"] is True


async def test_filter_by_date_range_excludes_out_of_range(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    await _attempt(client, warehouse_id, "x")

    resp = await client.get(
        "/visit-log",
        params={"date_from": "2099-01-01T00:00:00Z"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_filter_by_user_id(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    created = await client.post(
        "/users",
        json={"name": "E", "auth_type": "fingerprint", "credential": "good", "warehouse_ids": [warehouse_id]},
        headers=admin_headers,
    )
    user_id = created.json()["id"]
    await _attempt(client, warehouse_id, "good")
    await _attempt(client, warehouse_id, "unknown-elsewhere")

    resp = await client.get("/visit-log", params={"user_id": user_id}, headers=admin_headers)
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["user_id"] == user_id
