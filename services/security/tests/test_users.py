import uuid


async def _create_user(client, admin_headers, **overrides):
    body = {
        "name": "Alice",
        "auth_type": "fingerprint",
        "credential": "template-abc",
        "warehouse_ids": [],
    }
    body.update(overrides)
    resp = await client.post("/users", json=body, headers=admin_headers)
    assert resp.status_code == 201
    return resp.json()


async def test_create_user_requires_admin(client, customer_token):
    resp = await client.post(
        "/users",
        json={"name": "Alice", "auth_type": "fingerprint", "credential": "abc", "warehouse_ids": []},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


async def test_list_users_requires_admin(client, customer_token):
    resp = await client.get("/users", headers={"x-internal-token": customer_token})
    assert resp.status_code == 403


async def test_create_user_does_not_expose_credential(client, admin_headers):
    user = await _create_user(client, admin_headers)
    assert "credential" not in user
    assert user["name"] == "Alice"
    assert user["auth_type"] == "fingerprint"
    assert user["is_active"] is True


async def test_create_supplier_with_nfc(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    user = await _create_user(
        client,
        admin_headers,
        name="Acme Supplier",
        auth_type="nfc",
        credential="card-uid-123",
        warehouse_ids=[warehouse_id],
    )
    assert user["auth_type"] == "nfc"
    assert user["warehouse_ids"] == [warehouse_id]


async def test_list_users_filters_by_auth_type_and_is_active(client, admin_headers):
    await _create_user(client, admin_headers, name="Employee", auth_type="fingerprint", credential="t1")
    await _create_user(client, admin_headers, name="Supplier", auth_type="nfc", credential="c1")

    resp = await client.get("/users", params={"auth_type": "nfc"}, headers=admin_headers)
    assert resp.status_code == 200
    names = {u["name"] for u in resp.json()}
    assert names == {"Supplier"}

    resp = await client.get("/users", params={"is_active": "true"}, headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_update_user_name_and_active(client, admin_headers):
    user = await _create_user(client, admin_headers)

    resp = await client.patch(
        f"/users/{user['id']}",
        json={"name": "Alice B.", "is_active": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Alice B."
    assert body["is_active"] is False


async def test_update_user_warehouse_ids(client, admin_headers):
    user = await _create_user(client, admin_headers)
    warehouse_id = str(uuid.uuid4())

    resp = await client.patch(
        f"/users/{user['id']}",
        json={"warehouse_ids": [warehouse_id]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["warehouse_ids"] == [warehouse_id]


async def test_update_user_not_found(client, admin_headers):
    resp = await client.patch(f"/users/{uuid.uuid4()}", json={"name": "X"}, headers=admin_headers)
    assert resp.status_code == 404


async def test_create_user_lazily_creates_unseen_warehouse(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    await _create_user(client, admin_headers, warehouse_ids=[warehouse_id])

    resp = await client.get("/warehouses", headers=admin_headers)
    assert resp.status_code == 200
    assert [w["id"] for w in resp.json()] == [warehouse_id]


async def test_delete_user_revokes_access(client, admin_headers):
    user = await _create_user(client, admin_headers)

    resp = await client.delete(f"/users/{user['id']}", headers=admin_headers)
    assert resp.status_code == 204

    listed = await client.get("/users", headers=admin_headers)
    assert listed.json() == []
