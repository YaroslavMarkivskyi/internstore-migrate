import uuid


async def test_get_empty_cart(client, customer_token):
    resp = await client.get("/cart", headers={"x-internal-token": customer_token})
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


async def test_add_item_creates_cart(client, customer_token):
    product_id = str(uuid.uuid4())
    resp = await client.post(
        "/cart",
        json={"product_id": product_id, "quantity": 2},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 201
    assert resp.json() == {"items": [{"product_id": product_id, "quantity": 2}]}


async def test_add_item_twice_accumulates_quantity(client, customer_token):
    product_id = str(uuid.uuid4())
    headers = {"x-internal-token": customer_token}
    await client.post("/cart", json={"product_id": product_id, "quantity": 2}, headers=headers)
    resp = await client.post("/cart", json={"product_id": product_id, "quantity": 3}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["items"] == [{"product_id": product_id, "quantity": 5}]


async def test_update_item_quantity(client, customer_token):
    product_id = str(uuid.uuid4())
    headers = {"x-internal-token": customer_token}
    await client.post("/cart", json={"product_id": product_id, "quantity": 2}, headers=headers)

    resp = await client.put(f"/cart/items/{product_id}", json={"quantity": 9}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == [{"product_id": product_id, "quantity": 9}]


async def test_update_item_not_in_cart_404(client, customer_token):
    resp = await client.put(
        f"/cart/items/{uuid.uuid4()}",
        json={"quantity": 1},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 404


async def test_remove_item(client, customer_token):
    product_id = str(uuid.uuid4())
    headers = {"x-internal-token": customer_token}
    await client.post("/cart", json={"product_id": product_id, "quantity": 2}, headers=headers)

    resp = await client.delete(f"/cart/items/{product_id}", headers=headers)
    assert resp.status_code == 204

    get_resp = await client.get("/cart", headers=headers)
    assert get_resp.json() == {"items": []}


async def test_remove_item_not_in_cart_404(client, customer_token):
    resp = await client.delete(
        f"/cart/items/{uuid.uuid4()}",
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 404


async def test_carts_are_isolated_by_owner(client, customer_token, admin_token, guest_token):
    product_id = str(uuid.uuid4())
    await client.post(
        "/cart", json={"product_id": product_id, "quantity": 1}, headers={"x-internal-token": customer_token}
    )

    admin_resp = await client.get("/cart", headers={"x-internal-token": admin_token})
    assert admin_resp.json() == {"items": []}

    guest_resp = await client.get("/cart", headers={"x-internal-token": guest_token})
    assert guest_resp.json() == {"items": []}


async def test_guest_token_works_identically_to_customer(client, guest_token):
    product_id = str(uuid.uuid4())
    resp = await client.post(
        "/cart",
        json={"product_id": product_id, "quantity": 1},
        headers={"x-internal-token": guest_token},
    )
    assert resp.status_code == 201


async def test_cart_requires_internal_token(client):
    resp = await client.get("/cart")
    assert resp.status_code == 401
