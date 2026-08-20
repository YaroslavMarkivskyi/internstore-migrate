import uuid


async def test_charge_creates_payment(client):
    order_id = str(uuid.uuid4())
    resp = await client.post(
        "/charge",
        json={"order_id": order_id, "amount": 42.50, "payment_method": "card"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "charged"
    assert body["payment_id"]


async def test_charge_is_idempotent_by_order_id(client):
    order_id = str(uuid.uuid4())
    first = await client.post(
        "/charge",
        json={"order_id": order_id, "amount": 10.00, "payment_method": "card"},
    )
    second = await client.post(
        "/charge",
        json={"order_id": order_id, "amount": 10.00, "payment_method": "card"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    # Same payment, not a double charge.
    assert first.json()["payment_id"] == second.json()["payment_id"]


async def test_charge_fails_on_configured_amount_suffix(client):
    order_id = str(uuid.uuid4())
    resp = await client.post(
        "/charge",
        json={"order_id": order_id, "amount": 19.99, "payment_method": "card"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "failed"


async def test_refund_is_idempotent_by_payment_id(client):
    order_id = str(uuid.uuid4())
    charge_resp = await client.post(
        "/charge",
        json={"order_id": order_id, "amount": 10.00, "payment_method": "card"},
    )
    payment_id = charge_resp.json()["payment_id"]

    first_refund = await client.post("/refund", json={"payment_id": payment_id})
    second_refund = await client.post("/refund", json={"payment_id": payment_id})
    assert first_refund.status_code == 200
    assert second_refund.status_code == 200
    assert first_refund.json()["status"] == "refunded"
    assert second_refund.json()["status"] == "refunded"


async def test_refund_unknown_payment_returns_404(client):
    resp = await client.post("/refund", json={"payment_id": str(uuid.uuid4())})
    assert resp.status_code == 404
