async def create_category(client, admin_token, name="Drinks") -> str:
    resp = await client.post(
        "/categories",
        json={"name": name},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_create_product_requires_admin(client, customer_token, admin_token):
    category_id = await create_category(client, admin_token)
    resp = await client.post(
        "/products",
        json={"name": "Cola", "price": 1.5, "category_id": category_id},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


async def test_create_product_as_admin_succeeds(client, admin_token):
    category_id = await create_category(client, admin_token)
    resp = await client.post(
        "/products",
        json={
            "name": "Cola",
            "price": 1.5,
            "category_id": category_id,
            "description": "Fizzy drink",
            "min_temperature": 2,
            "max_temperature": 8,
        },
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Cola"
    assert body["category_id"] == category_id


async def test_create_product_unknown_category_rejected(client, admin_token):
    resp = await client.post(
        "/products",
        json={"name": "Cola", "price": 1.5, "category_id": "00000000-0000-0000-0000-000000000000"},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 422


async def test_create_product_non_positive_price_rejected(client, admin_token):
    category_id = await create_category(client, admin_token)
    resp = await client.post(
        "/products",
        json={"name": "Cola", "price": 0, "category_id": category_id},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 422


async def test_list_and_get_product(client, admin_token):
    category_id = await create_category(client, admin_token)
    created = await client.post(
        "/products",
        json={"name": "Cola", "price": 1.5, "category_id": category_id},
        headers={"x-internal-token": admin_token},
    )
    product_id = created.json()["id"]

    listed = await client.get("/products")
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()] == [product_id]

    fetched = await client.get(f"/products/{product_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Cola"


async def test_get_product_not_found(client):
    resp = await client.get("/products/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def create_product(client, admin_token, category_id, **overrides) -> str:
    payload = {"name": "Cola", "price": 1.5, "category_id": category_id, **overrides}
    resp = await client.post("/products", json=payload, headers={"x-internal-token": admin_token})
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_update_product_requires_admin(client, admin_token, customer_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)
    resp = await client.patch(
        f"/products/{product_id}",
        json={"price": 2.0},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


async def test_update_product_not_found(client, admin_token):
    resp = await client.patch(
        "/products/00000000-0000-0000-0000-000000000000",
        json={"price": 2.0},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 404


async def test_update_product_unknown_category_rejected(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)
    resp = await client.patch(
        f"/products/{product_id}",
        json={"category_id": "00000000-0000-0000-0000-000000000000"},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 422


async def test_update_product_partial_fields(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id, description="Original")
    resp = await client.patch(
        f"/products/{product_id}",
        json={"price": 3.5},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["price"] == 3.5
    assert body["description"] == "Original"


async def test_update_product_temperature_stages_outbox_event(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id, min_temperature=2, max_temperature=8)

    resp = await client.patch(
        f"/products/{product_id}",
        json={"max_temperature": 10},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 200

    from sqlalchemy import select

    from catalog.models import OutboxEvent

    async with client.app.state.session_factory() as session:
        result = await session.execute(select(OutboxEvent))
        events = list(result.scalars().all())

    assert len(events) == 1
    assert events[0].event_type == "ProductThresholdUpdated"
    assert events[0].payload["product_id"] == product_id
    assert events[0].payload["max_temperature"] == 10


async def test_new_product_is_published_by_default(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)

    fetched = await client.get(f"/products/{product_id}")
    assert fetched.json()["is_published"] is True


async def test_toggle_is_published(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)

    resp = await client.patch(
        f"/products/{product_id}",
        json={"is_published": False},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is False


async def test_delete_published_product_rejected(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)

    resp = await client.delete(f"/products/{product_id}", headers={"x-internal-token": admin_token})
    assert resp.status_code == 409

    still_there = await client.get(f"/products/{product_id}")
    assert still_there.status_code == 200


async def test_delete_unpublished_product_succeeds(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)
    await client.patch(
        f"/products/{product_id}",
        json={"is_published": False},
        headers={"x-internal-token": admin_token},
    )

    resp = await client.delete(f"/products/{product_id}", headers={"x-internal-token": admin_token})
    assert resp.status_code == 204

    gone = await client.get(f"/products/{product_id}")
    assert gone.status_code == 404


async def test_delete_product_requires_admin(client, admin_token, customer_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)

    resp = await client.delete(f"/products/{product_id}", headers={"x-internal-token": customer_token})
    assert resp.status_code == 403


async def test_delete_product_not_found(client, admin_token):
    resp = await client.delete(
        "/products/00000000-0000-0000-0000-000000000000", headers={"x-internal-token": admin_token}
    )
    assert resp.status_code == 404


async def test_update_product_without_temperature_change_stages_no_event(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id, min_temperature=2, max_temperature=8)

    resp = await client.patch(
        f"/products/{product_id}",
        json={"price": 4.0},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 200

    from sqlalchemy import select

    from catalog.models import OutboxEvent

    async with client.app.state.session_factory() as session:
        result = await session.execute(select(OutboxEvent))
        events = list(result.scalars().all())

    assert events == []
