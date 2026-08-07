import uuid

from tests.conftest import create_stock


async def test_reserve_stock_reserves_across_stocks(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())

    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)

    resp = await client.post(
        "/stocks/reserve",
        json={"order_id": order_id, "items": [{"product_id": product_id, "quantity": 3}]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"order_id": order_id, "status": "reserved"}

    # reserved_quantity isn't exposed on StockItemRead — assert the hold via
    # check-availability instead: 3 of the 5 units are now held, so only 2
    # remain available for a new reservation.
    availability = await client.post(
        "/stocks/check-availability",
        json={"items": [{"product_id": product_id, "quantity": 1}]},
        headers=headers,
    )
    assert availability.json()["items"][0]["available"] == 2


async def test_reserve_stock_insufficient(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())

    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 2}, headers=headers)

    resp = await client.post(
        "/stocks/reserve",
        json={"order_id": order_id, "items": [{"product_id": product_id, "quantity": 5}]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"order_id": order_id, "status": "insufficient_stock"}


async def test_reserve_stock_is_idempotent_by_order_id(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())

    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)

    first = await client.post(
        "/stocks/reserve",
        json={"order_id": order_id, "items": [{"product_id": product_id, "quantity": 3}]},
        headers=headers,
    )
    second = await client.post(
        "/stocks/reserve",
        json={"order_id": order_id, "items": [{"product_id": product_id, "quantity": 3}]},
        headers=headers,
    )
    assert first.json()["status"] == "reserved"
    # Retried activity call — must not double-reserve.
    assert second.json()["status"] == "reserved"


async def test_release_stock_frees_reserved_quantity(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())

    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)
    await client.post(
        "/stocks/reserve",
        json={"order_id": order_id, "items": [{"product_id": product_id, "quantity": 3}]},
        headers=headers,
    )

    resp = await client.post("/stocks/release", json={"order_id": order_id}, headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"order_id": order_id, "status": "released"}

    # Full quantity available again — a fresh reserve for the same amount
    # succeeds.
    again = await client.post(
        "/stocks/reserve",
        json={"order_id": str(uuid.uuid4()), "items": [{"product_id": product_id, "quantity": 5}]},
        headers=headers,
    )
    assert again.json()["status"] == "reserved"


async def test_release_stock_is_idempotent_by_order_id(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())

    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)
    await client.post(
        "/stocks/reserve",
        json={"order_id": order_id, "items": [{"product_id": product_id, "quantity": 3}]},
        headers=headers,
    )

    first = await client.post("/stocks/release", json={"order_id": order_id}, headers=headers)
    second = await client.post("/stocks/release", json={"order_id": order_id}, headers=headers)
    assert first.json()["status"] == "released"
    # Unbounded-retry compensation must not error on redelivery.
    assert second.json()["status"] == "not_found"


async def test_release_stock_unknown_order_returns_not_found(client, admin_token):
    headers = {"x-internal-token": admin_token}
    resp = await client.post("/stocks/release", json={"order_id": str(uuid.uuid4())}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_found"
