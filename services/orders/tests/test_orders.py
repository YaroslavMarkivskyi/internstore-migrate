import uuid

from tests.conftest import mint_internal_token

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
    customer_headers = customer_token
    admin_headers = admin_token

    await _checkout(client, customer_headers, fake_inventory_client, str(uuid.uuid4()))

    customer_orders = await client.get("/orders", headers=customer_headers)
    assert len(customer_orders.json()) == 1

    admin_orders = await client.get("/orders", headers=admin_headers)
    assert admin_orders.json() == []


async def test_get_order_by_id(client, customer_token, fake_inventory_client):
    headers = customer_token
    order = await _checkout(client, headers, fake_inventory_client, str(uuid.uuid4()))

    resp = await client.get(f"/orders/{order['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == order["id"]


async def test_get_order_belonging_to_someone_else_404(client, customer_token, fake_inventory_client):
    headers = customer_token
    order = await _checkout(client, headers, fake_inventory_client, str(uuid.uuid4()))

    # STR-140: OPA's owner-check (policies/orders.rego) replaces the
    # previous inline `order.owner_id != claims.sub` comparison -- a
    # different customer is still denied, still surfaced as 404 (not 403)
    # so the response doesn't leak that the order exists at all.
    other_customer_token = mint_internal_token(sub="customer-2", role="customer")
    resp = await client.get(f"/orders/{order['id']}", headers=other_customer_token)
    assert resp.status_code == 404


async def test_get_order_admin_can_view_any_order(client, customer_token, admin_token, fake_inventory_client):
    # STR-140: policies/orders.rego's admin-can-do-anything rule now
    # applies here too -- previously this endpoint had no admin bypass at
    # all (only the separate GET /orders/admin/{id} route did).
    headers = customer_token
    order = await _checkout(client, headers, fake_inventory_client, str(uuid.uuid4()))

    resp = await client.get(f"/orders/{order['id']}", headers=admin_token)
    assert resp.status_code == 200
    assert resp.json()["id"] == order["id"]


async def test_get_nonexistent_order_404(client, customer_token):
    resp = await client.get(f"/orders/{uuid.uuid4()}", headers=customer_token)
    assert resp.status_code == 404
