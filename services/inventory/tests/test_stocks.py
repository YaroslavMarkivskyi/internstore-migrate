import uuid

from sqlalchemy import select

from inventory.models import OutboxEvent
from tests.conftest import create_stock


async def test_list_stocks_empty(client):
    resp = await client.get("/stocks")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_stock_as_admin_succeeds(client, admin_token):
    resp = await client.post(
        "/stocks",
        json={"name": "Warehouse A", "temperature": 4.5},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Warehouse A"
    assert body["temperature"] == 4.5


async def test_create_stock_duplicate_name_rejected(client, admin_token):
    headers = {"x-internal-token": admin_token}
    first = await client.post("/stocks", json={"name": "Warehouse A"}, headers=headers)
    assert first.status_code == 201

    second = await client.post("/stocks", json={"name": "Warehouse A"}, headers=headers)
    assert second.status_code == 409


async def test_create_stock_name_too_short(client, admin_token):
    resp = await client.post(
        "/stocks",
        json={"name": "A"},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 422


async def test_list_stocks(client, admin_token):
    await create_stock(client, admin_token, name="Warehouse A")
    resp = await client.get("/stocks")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Warehouse A"
    assert body[0]["temperature"] is None


async def test_list_stock_items_not_found(client):
    resp = await client.get(f"/stocks/{uuid.uuid4()}/items")
    assert resp.status_code == 404


async def test_receive_stock_item_as_admin_succeeds(client, admin_token):
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    resp = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": product_id, "quantity": 5},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["product_id"] == product_id
    assert body["quantity"] == 5


async def test_receive_stock_item_accumulates_quantity(client, admin_token):
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    headers = {"x-internal-token": admin_token}

    first = await client.post(
        f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers
    )
    second = await client.post(
        f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 3}, headers=headers
    )

    assert first.json()["id"] == second.json()["id"]
    assert second.json()["quantity"] == 8


async def test_receive_stock_item_publishes_item_added(client, admin_token):
    """Regression test for STR-152/STR-153: build_receive_stock_item must
    stage ItemAdded on inventory-events, same as the pre-STR-149 route did
    -- Telemetry's handle_item_added is what creates the {store, product}
    threshold row that temperature-violation detection depends on."""
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    resp = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": product_id, "quantity": 5},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201

    async with client.app.state.session_factory() as session:
        outbox = (
            await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "ItemAdded"))
        ).scalars().all()
        assert len(outbox) == 1
        assert outbox[0].payload == {"stock_id": stock_id, "product_id": product_id}


async def test_receive_stock_item_unknown_stock(client, admin_token):
    resp = await client.post(
        f"/stocks/{uuid.uuid4()}/items",
        json={"product_id": str(uuid.uuid4()), "quantity": 5},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 404


async def test_list_stock_items(client, admin_token):
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": product_id, "quantity": 5},
        headers={"x-internal-token": admin_token},
    )

    resp = await client.get(f"/stocks/{stock_id}/items")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["product_id"] == product_id


async def test_move_stock_item_as_admin_succeeds(client, admin_token):
    headers = {"x-internal-token": admin_token}
    src = await create_stock(client, admin_token, name="Src")
    dst = await create_stock(client, admin_token, name="Dst")
    product_id = str(uuid.uuid4())
    created = await client.post(
        f"/stocks/{src}/items", json={"product_id": product_id, "quantity": 5}, headers=headers
    )
    item_id = created.json()["id"]

    resp = await client.post(
        f"/stocks/{src}/items/{item_id}/move",
        json={"to_stock_id": dst, "quantity": 2},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stock_id"] == dst
    assert body["product_id"] == product_id
    assert body["quantity"] == 2

    src_items = await client.get(f"/stocks/{src}/items")
    assert src_items.json()[0]["quantity"] == 3


async def test_move_stock_item_publishes_item_added_for_destination(client, admin_token):
    """Regression test for STR-153: the pre-STR-149 move_stock_item route
    staged ItemAdded for the *destination* stock (it now carries the
    product for the first time), but the STR-149 event-sourcing rewrite
    dropped it -- same class of bug as receive_stock_item's ItemAdded gap
    (STR-152), just not caught by that fix since it lives in a different
    build_* function."""
    headers = {"x-internal-token": admin_token}
    src = await create_stock(client, admin_token, name="Src")
    dst = await create_stock(client, admin_token, name="Dst")
    product_id = str(uuid.uuid4())
    created = await client.post(
        f"/stocks/{src}/items", json={"product_id": product_id, "quantity": 5}, headers=headers
    )
    item_id = created.json()["id"]

    resp = await client.post(
        f"/stocks/{src}/items/{item_id}/move",
        json={"to_stock_id": dst, "quantity": 2},
        headers=headers,
    )
    assert resp.status_code == 200

    async with client.app.state.session_factory() as session:
        outbox = (
            await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "ItemAdded"))
        ).scalars().all()
        # One from the initial receive into `src`, one from the move into `dst`.
        assert len(outbox) == 2
        assert outbox[1].payload == {"stock_id": dst, "product_id": product_id}


async def test_move_stock_item_insufficient_quantity(client, admin_token):
    headers = {"x-internal-token": admin_token}
    src = await create_stock(client, admin_token, name="Src")
    dst = await create_stock(client, admin_token, name="Dst")
    product_id = str(uuid.uuid4())
    created = await client.post(
        f"/stocks/{src}/items", json={"product_id": product_id, "quantity": 5}, headers=headers
    )
    item_id = created.json()["id"]

    resp = await client.post(
        f"/stocks/{src}/items/{item_id}/move",
        json={"to_stock_id": dst, "quantity": 10},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_move_stock_item_same_stock_rejected(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    created = await client.post(
        f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers
    )
    item_id = created.json()["id"]

    resp = await client.post(
        f"/stocks/{stock_id}/items/{item_id}/move",
        json={"to_stock_id": stock_id, "quantity": 1},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_move_stock_item_not_found(client, admin_token):
    headers = {"x-internal-token": admin_token}
    src = await create_stock(client, admin_token, name="Src")
    dst = await create_stock(client, admin_token, name="Dst")

    resp = await client.post(
        f"/stocks/{src}/items/{uuid.uuid4()}/move",
        json={"to_stock_id": dst, "quantity": 1},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_create_stock_with_humidity(client, admin_token):
    resp = await client.post(
        "/stocks",
        json={"name": "Warehouse A", "humidity": 55.5},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    assert resp.json()["humidity"] == 55.5


async def test_get_stock(client, admin_token):
    stock_id = await create_stock(client, admin_token, name="Warehouse A")
    resp = await client.get(f"/stocks/{stock_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Warehouse A"


async def test_get_stock_not_found(client):
    resp = await client.get(f"/stocks/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_update_stock_renames(client, admin_token):
    stock_id = await create_stock(client, admin_token, name="Warehouse A")
    resp = await client.patch(
        f"/stocks/{stock_id}",
        json={"name": "Warehouse B", "temperature": 3.0, "humidity": 40.0},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Warehouse B"
    assert body["temperature"] == 3.0
    assert body["humidity"] == 40.0


async def test_update_stock_duplicate_name_rejected(client, admin_token):
    headers = {"x-internal-token": admin_token}
    await create_stock(client, admin_token, name="Warehouse A")
    other_id = await create_stock(client, admin_token, name="Warehouse B")

    resp = await client.patch(f"/stocks/{other_id}", json={"name": "Warehouse A"}, headers=headers)
    assert resp.status_code == 409


async def test_update_stock_not_found(client, admin_token):
    resp = await client.patch(
        f"/stocks/{uuid.uuid4()}",
        json={"name": "Warehouse B"},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 404


async def test_delete_empty_stock_succeeds(client, admin_token):
    stock_id = await create_stock(client, admin_token)
    resp = await client.delete(f"/stocks/{stock_id}", headers={"x-internal-token": admin_token})
    assert resp.status_code == 204

    listed = await client.get("/stocks")
    assert listed.json() == []


async def test_delete_stock_with_quantity_rejected(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": str(uuid.uuid4()), "quantity": 5},
        headers=headers,
    )

    resp = await client.delete(f"/stocks/{stock_id}", headers=headers)
    assert resp.status_code == 409


async def test_delete_stock_not_found(client, admin_token):
    resp = await client.delete(f"/stocks/{uuid.uuid4()}", headers={"x-internal-token": admin_token})
    assert resp.status_code == 404


async def test_update_stock_item_quantity(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    created = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": str(uuid.uuid4()), "quantity": 5},
        headers=headers,
    )
    item_id = created.json()["id"]

    resp = await client.patch(
        f"/stocks/{stock_id}/items/{item_id}",
        json={"quantity": 12},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 12


async def test_update_stock_item_quantity_wrong_stock(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_a = await create_stock(client, admin_token, name="Stock A")
    stock_b = await create_stock(client, admin_token, name="Stock B")
    created = await client.post(
        f"/stocks/{stock_a}/items",
        json={"product_id": str(uuid.uuid4()), "quantity": 5},
        headers=headers,
    )
    item_id = created.json()["id"]

    resp = await client.patch(
        f"/stocks/{stock_b}/items/{item_id}",
        json={"quantity": 12},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_delete_stock_item_as_admin_succeeds(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    created = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": str(uuid.uuid4()), "quantity": 5},
        headers=headers,
    )
    item_id = created.json()["id"]

    resp = await client.delete(f"/stocks/{stock_id}/items/{item_id}", headers=headers)
    assert resp.status_code == 204

    remaining = await client.get(f"/stocks/{stock_id}/items")
    assert remaining.json() == []


async def test_delete_stock_item_not_found(client, admin_token):
    stock_id = await create_stock(client, admin_token)
    resp = await client.delete(
        f"/stocks/{stock_id}/items/{uuid.uuid4()}",
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 404


async def test_delete_stock_item_wrong_stock(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_a = await create_stock(client, admin_token, name="Stock A")
    stock_b = await create_stock(client, admin_token, name="Stock B")
    created = await client.post(
        f"/stocks/{stock_a}/items",
        json={"product_id": str(uuid.uuid4()), "quantity": 5},
        headers=headers,
    )
    item_id = created.json()["id"]

    resp = await client.delete(f"/stocks/{stock_b}/items/{item_id}", headers=headers)
    assert resp.status_code == 404


async def test_delete_stock_item_unpublishes_product_when_last_stock(client, admin_token, fake_catalog_client):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    created = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": product_id, "quantity": 5},
        headers=headers,
    )
    item_id = created.json()["id"]

    resp = await client.delete(f"/stocks/{stock_id}/items/{item_id}", headers=headers)
    assert resp.status_code == 204
    assert fake_catalog_client.unpublished == [product_id]


async def test_delete_stock_item_does_not_unpublish_when_other_stock_still_has_it(
    client, admin_token, fake_catalog_client
):
    headers = {"x-internal-token": admin_token}
    stock_a = await create_stock(client, admin_token, name="Stock A")
    stock_b = await create_stock(client, admin_token, name="Stock B")
    product_id = str(uuid.uuid4())
    await client.post(
        f"/stocks/{stock_a}/items", json={"product_id": product_id, "quantity": 5}, headers=headers
    )
    created_b = await client.post(
        f"/stocks/{stock_b}/items", json={"product_id": product_id, "quantity": 3}, headers=headers
    )
    item_id = created_b.json()["id"]

    resp = await client.delete(f"/stocks/{stock_b}/items/{item_id}", headers=headers)
    assert resp.status_code == 204
    assert fake_catalog_client.unpublished == []


async def test_update_stock_item_quantity_to_zero_unpublishes_product(client, admin_token, fake_catalog_client):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    created = await client.post(
        f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers
    )
    item_id = created.json()["id"]

    resp = await client.patch(
        f"/stocks/{stock_id}/items/{item_id}", json={"quantity": 0}, headers=headers
    )
    assert resp.status_code == 200
    assert fake_catalog_client.unpublished == [product_id]


async def test_update_stock_item_quantity_above_zero_does_not_unpublish(client, admin_token, fake_catalog_client):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    created = await client.post(
        f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers
    )
    item_id = created.json()["id"]

    resp = await client.patch(
        f"/stocks/{stock_id}/items/{item_id}", json={"quantity": 2}, headers=headers
    )
    assert resp.status_code == 200
    assert fake_catalog_client.unpublished == []
