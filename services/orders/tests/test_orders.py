import uuid

CHECKOUT_PAYLOAD = {
    "contact_name": "Jane Doe",
    "contact_email": "jane@example.com",
    "payment_method": "card",
}


async def _checkout(client, headers, fake_inventory_client, product_id: str) -> dict:
    await client.post("/cart", json={"product_id": product_id, "quantity": 1}, headers=headers)
    fake_inventory_client.set_sufficient([{"product_id": product_id, "quantity": 1}])
    resp = await client.post("/checkout", json=CHECKOUT_PAYLOAD, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def test_list_orders_only_own(client, customer_token, admin_token, fake_inventory_client):
    customer_headers = {"x-internal-token": customer_token}
    admin_headers = {"x-internal-token": admin_token}

    await _checkout(client, customer_headers, fake_inventory_client, str(uuid.uuid4()))

    customer_orders = await client.get("/orders", headers=customer_headers)
    assert len(customer_orders.json()) == 1

    admin_orders = await client.get("/orders", headers=admin_headers)
    assert admin_orders.json() == []


async def test_get_order_by_id(client, customer_token, fake_inventory_client):
    headers = {"x-internal-token": customer_token}
    order = await _checkout(client, headers, fake_inventory_client, str(uuid.uuid4()))

    resp = await client.get(f"/orders/{order['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == order["id"]


async def test_get_order_belonging_to_someone_else_404(client, customer_token, admin_token, fake_inventory_client):
    headers = {"x-internal-token": customer_token}
    order = await _checkout(client, headers, fake_inventory_client, str(uuid.uuid4()))

    resp = await client.get(f"/orders/{order['id']}", headers={"x-internal-token": admin_token})
    assert resp.status_code == 404


async def test_get_nonexistent_order_404(client, customer_token):
    resp = await client.get(f"/orders/{uuid.uuid4()}", headers={"x-internal-token": customer_token})
    assert resp.status_code == 404
