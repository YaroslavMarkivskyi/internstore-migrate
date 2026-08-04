import uuid

from tests.conftest import create_stock


async def test_list_stocks_empty(client):
    resp = await client.get("/stocks")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_stock_requires_admin(client, customer_token):
    resp = await client.post(
        "/stocks",
        json={"name": "Warehouse A"},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


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


async def test_create_stock_missing_token(client):
    resp = await client.post("/stocks", json={"name": "Warehouse A"})
    assert resp.status_code == 401


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


async def test_receive_stock_item_requires_admin(client, customer_token, admin_token):
    stock_id = await create_stock(client, admin_token)
    resp = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": str(uuid.uuid4()), "quantity": 5},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


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


async def test_move_stock_item_requires_admin(client, customer_token, admin_token):
    src = await create_stock(client, admin_token, name="Src")
    dst = await create_stock(client, admin_token, name="Dst")
    product_id = str(uuid.uuid4())
    created = await client.post(
        f"/stocks/{src}/items",
        json={"product_id": product_id, "quantity": 5},
        headers={"x-internal-token": admin_token},
    )
    item_id = created.json()["id"]

    resp = await client.post(
        f"/stocks/{src}/items/{item_id}/move",
        json={"to_stock_id": dst, "quantity": 2},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


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


async def test_update_stock_requires_admin(client, admin_token, customer_token):
    stock_id = await create_stock(client, admin_token)
    resp = await client.patch(
        f"/stocks/{stock_id}",
        json={"name": "Warehouse B"},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


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


async def test_delete_stock_requires_admin(client, admin_token, customer_token):
    stock_id = await create_stock(client, admin_token)
    resp = await client.delete(f"/stocks/{stock_id}", headers={"x-internal-token": customer_token})
    assert resp.status_code == 403


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


async def test_update_stock_item_quantity_requires_admin(client, admin_token, customer_token):
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
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


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


async def test_delete_stock_item_requires_admin(client, admin_token, customer_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    created = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": str(uuid.uuid4()), "quantity": 5},
        headers=headers,
    )
    item_id = created.json()["id"]

    resp = await client.delete(
        f"/stocks/{stock_id}/items/{item_id}",
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


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
