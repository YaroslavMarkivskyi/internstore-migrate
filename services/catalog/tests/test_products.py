async def create_category(client, admin_token, name="Drinks") -> str:
    resp = await client.post(
        "/categories",
        json={"name": name},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


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

    # A temperature change stages both: ProductThresholdUpdated (consumed by
    # Inventory) and ProductUpdated (consumed by AI Assistant to re-embed).
    assert len(events) == 2
    event_types = {event.event_type for event in events}
    assert event_types == {"ProductThresholdUpdated", "ProductUpdated"}

    threshold_event = next(e for e in events if e.event_type == "ProductThresholdUpdated")
    assert threshold_event.payload["product_id"] == product_id
    assert threshold_event.payload["max_temperature"] == 10


async def test_update_product_name_stages_product_updated_event(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)

    resp = await client.patch(
        f"/products/{product_id}",
        json={"name": "New name"},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 200

    from sqlalchemy import select

    from catalog.models import OutboxEvent

    async with client.app.state.session_factory() as session:
        result = await session.execute(select(OutboxEvent))
        events = list(result.scalars().all())

    assert len(events) == 1
    assert events[0].event_type == "ProductUpdated"
    assert events[0].payload["product_id"] == product_id
    assert events[0].payload["name"] == "New name"
    assert "category_name" in events[0].payload


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

    # Soft delete: GET /products/{id} still resolves (Orders' catalog_client
    # needs this for historical pricing, Inventory's stock-item join needs
    # it for name/price/category) -- only the is_deleted flag flips.
    still_resolvable = await client.get(f"/products/{product_id}")
    assert still_resolvable.status_code == 200
    assert still_resolvable.json()["is_deleted"] is True

    # But it's gone as far as further admin mutation is concerned.
    reupdate = await client.patch(
        f"/products/{product_id}",
        json={"name": "New Name"},
        headers={"x-internal-token": admin_token},
    )
    assert reupdate.status_code == 404

    redelete = await client.delete(f"/products/{product_id}", headers={"x-internal-token": admin_token})
    assert redelete.status_code == 404


async def test_delete_product_stages_product_deleted_event(client, admin_token):
    """STR-148: without this, AI Assistant's product_embeddings row for a
    deleted product never gets cleaned up, and search_products keeps
    surfacing a product_id that no longer exists at all — found live."""
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)
    await client.patch(
        f"/products/{product_id}",
        json={"is_published": False},
        headers={"x-internal-token": admin_token},
    )

    resp = await client.delete(f"/products/{product_id}", headers={"x-internal-token": admin_token})
    assert resp.status_code == 204

    from sqlalchemy import select

    from catalog.models import OutboxEvent

    async with client.app.state.session_factory() as session:
        result = await session.execute(select(OutboxEvent))
        events = list(result.scalars().all())

    deleted_events = [e for e in events if e.event_type == "ProductDeleted"]
    assert len(deleted_events) == 1
    assert deleted_events[0].payload == {"product_id": product_id}


async def test_delete_product_not_found(client, admin_token):
    resp = await client.delete(
        "/products/00000000-0000-0000-0000-000000000000", headers={"x-internal-token": admin_token}
    )
    assert resp.status_code == 404


async def test_update_product_without_temperature_change_stages_no_threshold_event(client, admin_token):
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

    # No temperature fields changed, so no ProductThresholdUpdated — but any
    # field change (price here) still stages ProductUpdated for AI
    # Assistant's re-embedding consumer.
    assert [e.event_type for e in events] == ["ProductUpdated"]


async def test_republish_rejected_when_out_of_stock(client, admin_token, fake_inventory_client):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)
    await client.patch(
        f"/products/{product_id}",
        json={"is_published": False},
        headers={"x-internal-token": admin_token},
    )
    fake_inventory_client.set_quantity(product_id, 0)

    resp = await client.patch(
        f"/products/{product_id}",
        json={"is_published": True},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 422

    still_unpublished = await client.get(f"/products/{product_id}")
    assert still_unpublished.json()["is_published"] is False


async def test_republish_succeeds_when_in_stock(client, admin_token, fake_inventory_client):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)
    await client.patch(
        f"/products/{product_id}",
        json={"is_published": False},
        headers={"x-internal-token": admin_token},
    )
    fake_inventory_client.set_quantity(product_id, 5)

    resp = await client.patch(
        f"/products/{product_id}",
        json={"is_published": True},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is True
