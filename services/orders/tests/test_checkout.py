import uuid

CHECKOUT_PAYLOAD = {
    "contact_name": "Jane Doe",
    "contact_email": "jane@example.com",
    "contact_phone": "+15551234567",
    "payment_method": "card",
}


async def _add_item(client, headers, product_id: str, quantity: int = 2) -> None:
    resp = await client.post("/cart", json={"product_id": product_id, "quantity": quantity}, headers=headers)
    assert resp.status_code == 201


async def test_checkout_happy_path_creates_order_and_clears_cart(client, customer_token, fake_inventory_client):
    headers = {"x-internal-token": customer_token}
    product_id = str(uuid.uuid4())
    await _add_item(client, headers, product_id, quantity=2)
    fake_inventory_client.set_sufficient([{"product_id": product_id, "quantity": 2}])

    resp = await client.post("/checkout", json=CHECKOUT_PAYLOAD, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "new"
    assert body["items"] == [{"product_id": product_id, "quantity": 2}]
    assert body["contact_email"] == "jane@example.com"

    cart_resp = await client.get("/cart", headers=headers)
    assert cart_resp.json() == {"items": []}

    # request-shape assurance: the caller's own internal token was forwarded
    assert fake_inventory_client.last_call is not None
    _, forwarded_token = fake_inventory_client.last_call
    assert forwarded_token == customer_token


async def test_checkout_insufficient_stock_returns_409_and_creates_no_order(
    client, customer_token, fake_inventory_client
):
    headers = {"x-internal-token": customer_token}
    product_id = str(uuid.uuid4())
    await _add_item(client, headers, product_id, quantity=10)
    fake_inventory_client.set_insufficient(
        [{"product_id": product_id, "requested": 10, "available": 3, "sufficient": False}]
    )

    resp = await client.post("/checkout", json=CHECKOUT_PAYLOAD, headers=headers)
    assert resp.status_code == 409
    body = resp.json()
    assert body["items"][0]["available"] == 3
    assert body["items"][0]["sufficient"] is False

    orders_resp = await client.get("/orders", headers=headers)
    assert orders_resp.json() == []

    # cart is untouched on a failed checkout
    cart_resp = await client.get("/cart", headers=headers)
    assert cart_resp.json()["items"] == [{"product_id": product_id, "quantity": 10}]


async def test_checkout_inventory_unavailable_returns_503(client, customer_token, fake_inventory_client):
    headers = {"x-internal-token": customer_token}
    product_id = str(uuid.uuid4())
    await _add_item(client, headers, product_id)
    fake_inventory_client.set_unavailable()

    resp = await client.post("/checkout", json=CHECKOUT_PAYLOAD, headers=headers)
    assert resp.status_code == 503
    assert "retry_after_seconds" in resp.json()

    orders_resp = await client.get("/orders", headers=headers)
    assert orders_resp.json() == []


async def test_checkout_empty_cart_returns_422(client, customer_token):
    resp = await client.post("/checkout", json=CHECKOUT_PAYLOAD, headers={"x-internal-token": customer_token})
    assert resp.status_code == 422


async def test_guest_checkout_works(client, guest_token, fake_inventory_client):
    headers = {"x-internal-token": guest_token}
    product_id = str(uuid.uuid4())
    await _add_item(client, headers, product_id, quantity=1)
    fake_inventory_client.set_sufficient([{"product_id": product_id, "quantity": 1}])

    resp = await client.post("/checkout", json=CHECKOUT_PAYLOAD, headers=headers)
    assert resp.status_code == 201
