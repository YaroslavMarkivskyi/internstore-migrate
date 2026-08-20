import uuid


async def test_list_warehouses_empty(client, admin_headers):
    resp = await client.get("/warehouses", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_lazy_create_on_first_auth_attempt(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    await client.post("/auth/fingerprint", json={"warehouse_id": warehouse_id, "fingerprint_template": "x"})

    resp = await client.get("/warehouses", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == warehouse_id
    assert body[0]["name"] == warehouse_id


async def test_patch_rename(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    await client.post("/auth/nfc", json={"warehouse_id": warehouse_id, "card_uid": "x"})

    resp = await client.patch(f"/warehouses/{warehouse_id}", json={"name": "Main Warehouse"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Main Warehouse"


async def test_patch_not_found(client, admin_headers):
    resp = await client.patch(f"/warehouses/{uuid.uuid4()}", json={"name": "X"}, headers=admin_headers)
    assert resp.status_code == 404
