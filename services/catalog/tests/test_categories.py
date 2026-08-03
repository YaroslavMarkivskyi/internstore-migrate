async def test_list_categories_empty(client):
    resp = await client.get("/categories")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_category_requires_admin(client, customer_token):
    resp = await client.post(
        "/categories",
        json={"name": "Snacks"},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


async def test_list_categories_allows_guest_token(client, guest_token):
    # Catalog browsing is guest-allowed at the Gateway (see
    # auth-backend's GUEST_ALLOWED_PATH_PREFIXES) — a guest-role internal
    # token must pass Catalog's own verification too, not just be rejected
    # for lacking the admin role.
    resp = await client.get("/categories", headers={"x-internal-token": guest_token})
    assert resp.status_code == 200


async def test_create_category_rejects_guest(client, guest_token):
    resp = await client.post(
        "/categories",
        json={"name": "Snacks"},
        headers={"x-internal-token": guest_token},
    )
    assert resp.status_code == 403


async def test_create_category_as_admin_succeeds(client, admin_token):
    resp = await client.post(
        "/categories",
        json={"name": "Snacks"},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Snacks"

    listed = await client.get("/categories")
    assert [c["name"] for c in listed.json()] == ["Snacks"]


async def test_create_category_missing_token(client):
    resp = await client.post("/categories", json={"name": "Snacks"})
    assert resp.status_code == 401


async def test_create_category_name_too_short(client, admin_token):
    resp = await client.post(
        "/categories",
        json={"name": "ab"},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 422


async def test_create_category_duplicate_name_rejected(client, admin_token):
    headers = {"x-internal-token": admin_token}
    first = await client.post("/categories", json={"name": "Drinks"}, headers=headers)
    assert first.status_code == 201

    second = await client.post("/categories", json={"name": "Drinks"}, headers=headers)
    assert second.status_code == 409
