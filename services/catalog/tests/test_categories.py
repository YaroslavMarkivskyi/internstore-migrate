async def test_list_categories_empty(client):
    resp = await client.get("/categories")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_categories_allows_guest_token(client, guest_token):
    # Catalog browsing is guest-allowed at the Gateway (see
    # auth-backend's GUEST_ALLOWED_PATH_PREFIXES) — GET never required a
    # token in the first place, guest or otherwise (see
    # nginx/internal-gate/catalog.conf).
    resp = await client.get("/categories", headers={"x-internal-token": guest_token})
    assert resp.status_code == 200


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


async def create_category(client, admin_token, name="Drinks") -> str:
    resp = await client.post(
        "/categories",
        json={"name": name},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_product(client, admin_token, category_id, name="Cola") -> str:
    resp = await client.post(
        "/products",
        json={"name": name, "price": 1.5, "category_id": category_id},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_update_category_renames(client, admin_token):
    category_id = await create_category(client, admin_token)
    resp = await client.patch(
        f"/categories/{category_id}",
        json={"name": "Beverages"},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Beverages"


async def test_update_category_duplicate_name_rejected(client, admin_token):
    headers = {"x-internal-token": admin_token}
    await create_category(client, admin_token, name="Drinks")
    other_id = await create_category(client, admin_token, name="Snacks")

    resp = await client.patch(f"/categories/{other_id}", json={"name": "Drinks"}, headers=headers)
    assert resp.status_code == 409


async def test_update_category_not_found(client, admin_token):
    resp = await client.patch(
        "/categories/00000000-0000-0000-0000-000000000000",
        json={"name": "Beverages"},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 404


async def test_delete_empty_category_succeeds(client, admin_token):
    category_id = await create_category(client, admin_token)
    resp = await client.delete(f"/categories/{category_id}", headers={"x-internal-token": admin_token})
    assert resp.status_code == 204

    listed = await client.get("/categories")
    assert listed.json() == []


async def test_delete_category_not_found(client, admin_token):
    resp = await client.delete(
        "/categories/00000000-0000-0000-0000-000000000000",
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 404


async def test_delete_category_with_products_no_mode_rejected(client, admin_token):
    category_id = await create_category(client, admin_token)
    await create_product(client, admin_token, category_id)

    resp = await client.delete(f"/categories/{category_id}", headers={"x-internal-token": admin_token})
    assert resp.status_code == 409


async def test_delete_category_move_mode_reassigns_products(client, admin_token):
    headers = {"x-internal-token": admin_token}
    source_id = await create_category(client, admin_token, name="Drinks")
    target_id = await create_category(client, admin_token, name="Snacks")
    product_id = await create_product(client, admin_token, source_id)

    resp = await client.request(
        "DELETE",
        f"/categories/{source_id}",
        json={"deletion_mode": "move", "target_category_id": target_id},
        headers=headers,
    )
    assert resp.status_code == 204

    product = await client.get(f"/products/{product_id}")
    assert product.json()["category_id"] == target_id


async def test_delete_category_move_mode_requires_target(client, admin_token):
    category_id = await create_category(client, admin_token)
    await create_product(client, admin_token, category_id)

    resp = await client.request(
        "DELETE",
        f"/categories/{category_id}",
        json={"deletion_mode": "move"},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 422


async def test_delete_category_unpublish_and_delete_moves_to_uncategorized(client, admin_token):
    headers = {"x-internal-token": admin_token}
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)

    resp = await client.request(
        "DELETE",
        f"/categories/{category_id}",
        json={"deletion_mode": "unpublish_and_delete"},
        headers=headers,
    )
    assert resp.status_code == 204

    product = (await client.get(f"/products/{product_id}")).json()
    assert product["is_published"] is False

    categories = (await client.get("/categories")).json()
    uncategorized = next(c for c in categories if c["name"] == "Uncategorized")
    assert product["category_id"] == uncategorized["id"]


async def test_delete_category_unpublish_and_delete_reuses_uncategorized(client, admin_token):
    headers = {"x-internal-token": admin_token}
    first_id = await create_category(client, admin_token, name="Drinks")
    await create_product(client, admin_token, first_id)
    await client.request(
        "DELETE",
        f"/categories/{first_id}",
        json={"deletion_mode": "unpublish_and_delete"},
        headers=headers,
    )

    second_id = await create_category(client, admin_token, name="Snacks")
    await create_product(client, admin_token, second_id)
    await client.request(
        "DELETE",
        f"/categories/{second_id}",
        json={"deletion_mode": "unpublish_and_delete"},
        headers=headers,
    )

    categories = (await client.get("/categories")).json()
    uncategorized = [c for c in categories if c["name"] == "Uncategorized"]
    assert len(uncategorized) == 1
