import json
import uuid

from sqlalchemy import select

from orders.models import Order, OrderStatus, OutboxEvent

CHECKOUT_PAYLOAD = {
    "contact_name": "Jane Doe",
    "contact_email": "jane@example.com",
    "payment_method": "card",
}

CASH_ON_DELIVERY_PAYLOAD = {**CHECKOUT_PAYLOAD, "payment_method": "cash_on_delivery"}


async def _create_order(client, headers, fake_inventory_client, payload=CHECKOUT_PAYLOAD, price: float = 9.99):
    product_id = str(uuid.uuid4())
    await client.post("/cart", json={"product_id": product_id, "quantity": 2}, headers=headers)
    fake_inventory_client.set_sufficient([{"product_id": product_id, "quantity": 2}])
    resp = await client.post("/checkout", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"], product_id, price


async def _set_status(client, order_id: str, status: OrderStatus) -> None:
    async with client.app.state.session_factory() as session:
        order = await session.get(Order, uuid.UUID(order_id))
        order.status = status
        await session.commit()


def _stripe_event(event_type: str, intent_id: str) -> bytes:
    return json.dumps({"type": event_type, "data": {"object": {"id": intent_id}}}).encode()


async def test_create_payment_intent_prices_from_catalog_not_client(
    client, customer_token, fake_inventory_client, fake_catalog_client, fake_stripe_client
):
    headers = {"x-internal-token": customer_token}
    order_id, product_id, price = await _create_order(client, headers, fake_inventory_client, price=9.99)
    await _set_status(client, order_id, OrderStatus.PENDING)
    fake_catalog_client.set_price(product_id, price)

    resp = await client.post(f"/orders/{order_id}/payment-intent", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["client_secret"] == "pi_fake_1_secret"

    # 2 units * $9.99 = $19.98 -> 1998 cents. Amount comes entirely from
    # fake_catalog_client's price, never from anything in the request.
    assert fake_stripe_client.created_intents == [
        {"amount_cents": 1998, "order_id": order_id, "id": "pi_fake_1"}
    ]

    async with client.app.state.session_factory() as session:
        order = await session.get(Order, uuid.UUID(order_id))
        assert order.stripe_payment_intent_id == "pi_fake_1"


async def test_create_payment_intent_rejects_cash_on_delivery(
    client, customer_token, fake_inventory_client
):
    headers = {"x-internal-token": customer_token}
    order_id, _, _ = await _create_order(client, headers, fake_inventory_client, payload=CASH_ON_DELIVERY_PAYLOAD)
    await _set_status(client, order_id, OrderStatus.PENDING)

    resp = await client.post(f"/orders/{order_id}/payment-intent", headers=headers)
    assert resp.status_code == 422


async def test_create_payment_intent_rejects_non_pending_order(
    client, customer_token, fake_inventory_client
):
    headers = {"x-internal-token": customer_token}
    order_id, _, _ = await _create_order(client, headers, fake_inventory_client)  # still "new"

    resp = await client.post(f"/orders/{order_id}/payment-intent", headers=headers)
    assert resp.status_code == 409


async def test_create_payment_intent_other_owners_order_returns_404(
    client, customer_token, guest_token, fake_inventory_client
):
    order_id, _, _ = await _create_order(client, {"x-internal-token": customer_token}, fake_inventory_client)
    await _set_status(client, order_id, OrderStatus.PENDING)

    resp = await client.post(
        f"/orders/{order_id}/payment-intent", headers={"x-internal-token": guest_token}
    )
    assert resp.status_code == 404


async def test_stripe_webhook_marks_order_paid(
    client, customer_token, fake_inventory_client, fake_catalog_client
):
    headers = {"x-internal-token": customer_token}
    order_id, product_id, price = await _create_order(client, headers, fake_inventory_client)
    await _set_status(client, order_id, OrderStatus.PENDING)
    fake_catalog_client.set_price(product_id, price)

    intent_resp = await client.post(f"/orders/{order_id}/payment-intent", headers=headers)
    assert intent_resp.status_code == 200

    webhook_resp = await client.post(
        "/webhooks/stripe",
        content=_stripe_event("payment_intent.succeeded", "pi_fake_1"),
        headers={"stripe-signature": "irrelevant-in-tests"},
    )
    assert webhook_resp.status_code == 200

    async with client.app.state.session_factory() as session:
        order = await session.get(Order, uuid.UUID(order_id))
        assert order.status == OrderStatus.PAID

        result = await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "PaymentConfirmed"))
        rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].payload["order_id"] == order_id


async def test_stripe_webhook_unknown_payment_intent_is_a_no_op(client):
    resp = await client.post(
        "/webhooks/stripe",
        content=_stripe_event("payment_intent.succeeded", "pi_does_not_exist"),
        headers={"stripe-signature": "irrelevant-in-tests"},
    )
    assert resp.status_code == 200


async def test_stripe_webhook_missing_signature_header_returns_400(client):
    resp = await client.post(
        "/webhooks/stripe",
        content=_stripe_event("payment_intent.succeeded", "pi_fake_1"),
    )
    assert resp.status_code == 400


async def test_admin_pay_confirms_cash_on_delivery_order(
    client, customer_token, admin_token, fake_inventory_client
):
    order_id, _, _ = await _create_order(
        client, {"x-internal-token": customer_token}, fake_inventory_client, payload=CASH_ON_DELIVERY_PAYLOAD
    )
    await _set_status(client, order_id, OrderStatus.PENDING)

    resp = await client.post(f"/admin/{order_id}/pay", headers={"x-internal-token": admin_token})
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"


async def test_admin_pay_rejects_non_admin(client, customer_token, fake_inventory_client):
    order_id, _, _ = await _create_order(
        client, {"x-internal-token": customer_token}, fake_inventory_client, payload=CASH_ON_DELIVERY_PAYLOAD
    )
    await _set_status(client, order_id, OrderStatus.PENDING)

    resp = await client.post(f"/admin/{order_id}/pay", headers={"x-internal-token": customer_token})
    assert resp.status_code == 403


async def test_admin_pay_non_pending_order_returns_409(client, customer_token, admin_token, fake_inventory_client):
    order_id, _, _ = await _create_order(client, {"x-internal-token": customer_token}, fake_inventory_client)

    resp = await client.post(f"/admin/{order_id}/pay", headers={"x-internal-token": admin_token})
    assert resp.status_code == 409
