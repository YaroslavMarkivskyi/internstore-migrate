import uuid

from orders.models import Order, OrderStatus
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


async def _set_status(client, order_id: str, status: OrderStatus) -> None:
    async with client.app.state.session_factory() as session:
        order = await session.get(Order, uuid.UUID(order_id))
        order.status = status
        await session.commit()


async def test_list_orders_admin_sees_all_customers(
    client, customer_token, admin_token, fake_inventory_client
):
    customer_headers = customer_token
    admin_headers = admin_token

    order = await _checkout(client, customer_headers, fake_inventory_client, str(uuid.uuid4()))

    resp = await client.get("/admin", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == order["id"]
    assert body[0]["customer"]


async def test_get_order_admin_sees_other_customers_order(
    client, customer_token, admin_token, fake_inventory_client
):
    customer_headers = customer_token
    order = await _checkout(client, customer_headers, fake_inventory_client, str(uuid.uuid4()))

    resp = await client.get(f"/admin/{order['id']}", headers=admin_token)
    assert resp.status_code == 200
    assert resp.json()["id"] == order["id"]


async def test_get_nonexistent_order_admin_404(client, admin_token):
    resp = await client.get(f"/admin/{uuid.uuid4()}", headers=admin_token)
    assert resp.status_code == 404


async def test_list_orders_admin_filters_by_owner_id(
    client, customer_token, admin_token, guest_token, fake_inventory_client
):
    customer_headers = customer_token
    guest_headers = guest_token

    customer_order = await _checkout(client, customer_headers, fake_inventory_client, str(uuid.uuid4()))
    await _checkout(client, guest_headers, fake_inventory_client, str(uuid.uuid4()))

    resp = await client.get(
        "/admin", params={"owner_id": "customer-1"}, headers=admin_token
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == customer_order["id"]


async def test_list_orders_admin_accepts_assistant_role(client, customer_token, fake_inventory_client):
    customer_headers = customer_token
    order = await _checkout(client, customer_headers, fake_inventory_client, str(uuid.uuid4()))

    assistant_token = mint_internal_token(sub="ai-assistant", role="assistant")
    resp = await client.get(
        "/admin", params={"owner_id": "customer-1"}, headers=assistant_token
    )
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == order["id"]


async def test_ship_order_admin_marks_paid_order_done(
    client, customer_token, admin_token, fake_inventory_client
):
    order = await _checkout(client, customer_token, fake_inventory_client, str(uuid.uuid4()))
    await _set_status(client, order["id"], OrderStatus.PAID)

    resp = await client.post(f"/admin/{order['id']}/ship", headers=admin_token)
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


async def test_ship_order_admin_non_paid_order_returns_409(
    client, customer_token, admin_token, fake_inventory_client
):
    order = await _checkout(client, customer_token, fake_inventory_client, str(uuid.uuid4()))

    resp = await client.post(f"/admin/{order['id']}/ship", headers=admin_token)
    assert resp.status_code == 409


async def test_ship_nonexistent_order_admin_404(client, admin_token):
    resp = await client.post(f"/admin/{uuid.uuid4()}/ship", headers=admin_token)
    assert resp.status_code == 404
