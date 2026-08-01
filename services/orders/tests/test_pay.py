import uuid

from sqlalchemy import select

from orders.models import Order, OrderStatus, OutboxEvent

CHECKOUT_PAYLOAD = {
    "contact_name": "Jane Doe",
    "contact_email": "jane@example.com",
    "payment_method": "card",
}


async def _create_order(client, headers, fake_inventory_client) -> str:
    product_id = str(uuid.uuid4())
    await client.post("/cart", json={"product_id": product_id, "quantity": 1}, headers=headers)
    fake_inventory_client.set_sufficient([{"product_id": product_id, "quantity": 1}])
    resp = await client.post("/checkout", json=CHECKOUT_PAYLOAD, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


async def _set_status(client, order_id: str, status: OrderStatus) -> None:
    async with client.app.state.session_factory() as session:
        order = await session.get(Order, uuid.UUID(order_id))
        order.status = status
        await session.commit()


async def test_pay_pending_order_transitions_to_paid_and_stages_outbox_event(
    client, customer_token, fake_inventory_client
):
    headers = {"x-internal-token": customer_token}
    order_id = await _create_order(client, headers, fake_inventory_client)
    await _set_status(client, order_id, OrderStatus.PENDING)

    resp = await client.post(f"/orders/{order_id}/pay", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"

    async with client.app.state.session_factory() as session:
        result = await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "PaymentConfirmed"))
        rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].payload["order_id"] == order_id


async def test_pay_non_pending_order_returns_409(client, customer_token, fake_inventory_client):
    headers = {"x-internal-token": customer_token}
    order_id = await _create_order(client, headers, fake_inventory_client)  # still "new", not pending

    resp = await client.post(f"/orders/{order_id}/pay", headers=headers)
    assert resp.status_code == 409


async def test_pay_other_owners_order_returns_404(client, customer_token, guest_token, fake_inventory_client):
    order_id = await _create_order(client, {"x-internal-token": customer_token}, fake_inventory_client)
    await _set_status(client, order_id, OrderStatus.PENDING)

    resp = await client.post(f"/orders/{order_id}/pay", headers={"x-internal-token": guest_token})
    assert resp.status_code == 404


async def test_pay_unknown_order_returns_404(client, customer_token):
    resp = await client.post(f"/orders/{uuid.uuid4()}/pay", headers={"x-internal-token": customer_token})
    assert resp.status_code == 404
