import uuid


async def _register_employee(client, admin_headers, warehouse_id, credential="fp-template-1", is_active=True):
    resp = await client.post(
        "/users",
        json={
            "name": "Employee",
            "auth_type": "fingerprint",
            "credential": credential,
            "warehouse_ids": [warehouse_id],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]
    if not is_active:
        patch = await client.patch(f"/users/{user_id}", json={"is_active": False}, headers=admin_headers)
        assert patch.status_code == 200
    return user_id


async def _register_supplier(client, admin_headers, warehouse_id, card_uid="card-uid-1"):
    resp = await client.post(
        "/users",
        json={"name": "Supplier", "auth_type": "nfc", "credential": card_uid, "warehouse_ids": [warehouse_id]},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_fingerprint_happy_path_allowed(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    user_id = await _register_employee(client, admin_headers, warehouse_id)

    resp = await client.post(
        "/auth/fingerprint", json={"warehouse_id": warehouse_id, "fingerprint_template": "fp-template-1"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is True
    assert body["user_id"] == user_id
    assert body["denial_reason"] is None


async def test_nfc_happy_path_allowed(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    user_id = await _register_supplier(client, admin_headers, warehouse_id)

    resp = await client.post("/auth/nfc", json={"warehouse_id": warehouse_id, "card_uid": "card-uid-1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is True
    assert body["user_id"] == user_id


async def test_unknown_fingerprint_denied(client):
    warehouse_id = str(uuid.uuid4())
    resp = await client.post(
        "/auth/fingerprint", json={"warehouse_id": warehouse_id, "fingerprint_template": "no-such-template"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is False
    assert body["user_id"] is None
    assert body["denial_reason"] == "unknown credential"


async def test_unknown_nfc_card_denied(client):
    warehouse_id = str(uuid.uuid4())
    resp = await client.post("/auth/nfc", json={"warehouse_id": warehouse_id, "card_uid": "no-such-card"})
    assert resp.status_code == 200
    assert resp.json()["allowed"] is False


async def test_inactive_user_denied(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    user_id = await _register_employee(client, admin_headers, warehouse_id, is_active=False)

    resp = await client.post(
        "/auth/fingerprint", json={"warehouse_id": warehouse_id, "fingerprint_template": "fp-template-1"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is False
    assert body["user_id"] == user_id
    assert body["denial_reason"] == "inactive user"


async def test_no_access_rule_for_warehouse_denied(client, admin_headers):
    granted_warehouse = str(uuid.uuid4())
    other_warehouse = str(uuid.uuid4())
    user_id = await _register_employee(client, admin_headers, granted_warehouse)

    resp = await client.post(
        "/auth/fingerprint", json={"warehouse_id": other_warehouse, "fingerprint_template": "fp-template-1"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is False
    assert body["user_id"] == user_id
    assert body["denial_reason"] == "no access to this warehouse"


async def test_visit_log_row_created_with_video_url_on_success(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    await _register_employee(client, admin_headers, warehouse_id)

    await client.post("/auth/fingerprint", json={"warehouse_id": warehouse_id, "fingerprint_template": "fp-template-1"})

    resp = await client.get("/visit-log", headers=admin_headers)
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["success"] is True
    assert entries[0]["video_url"] is not None
    assert entries[0]["warehouse_id"] == warehouse_id


async def test_visit_log_row_created_on_denial(client, admin_headers):
    warehouse_id = str(uuid.uuid4())
    await client.post(
        "/auth/fingerprint", json={"warehouse_id": warehouse_id, "fingerprint_template": "no-such-template"}
    )

    resp = await client.get("/visit-log", headers=admin_headers)
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["success"] is False
    assert entries[0]["denial_reason"] == "unknown credential"
    assert entries[0]["video_url"] is not None
