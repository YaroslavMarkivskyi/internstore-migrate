import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.models import Stock, StockItem
from tests.conftest import create_stock


@pytest.fixture
async def session(client) -> AsyncSession:
    async with client.app.state.session_factory() as session:
        yield session


async def _make_stock_item(session: AsyncSession, quantity: int, reserved_quantity: int, product_id: uuid.UUID) -> StockItem:
    stock = Stock(name=f"Warehouse {uuid.uuid4()}")
    session.add(stock)
    await session.flush()
    item = StockItem(stock_id=stock.id, product_id=product_id, quantity=quantity, reserved_quantity=reserved_quantity)
    session.add(item)
    await session.commit()
    return item


async def test_check_availability_sufficient(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_a = await create_stock(client, admin_token, name="Stock A")
    stock_b = await create_stock(client, admin_token, name="Stock B")
    product_id = str(uuid.uuid4())

    await client.post(f"/stocks/{stock_a}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)
    await client.post(f"/stocks/{stock_b}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)

    resp = await client.post(
        "/stocks/check-availability",
        json={"items": [{"product_id": product_id, "quantity": 10}]},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sufficient"] is True
    assert body["items"] == [
        {"product_id": product_id, "requested": 10, "available": 10, "sufficient": True}
    ]


async def test_check_availability_insufficient(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())

    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 3}, headers=headers)

    resp = await client.post(
        "/stocks/check-availability",
        json={"items": [{"product_id": product_id, "quantity": 10}]},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sufficient"] is False
    assert body["items"][0]["available"] == 3
    assert body["items"][0]["sufficient"] is False


async def test_check_availability_unknown_product_is_zero_available(client, customer_token):
    resp = await client.post(
        "/stocks/check-availability",
        json={"items": [{"product_id": str(uuid.uuid4()), "quantity": 1}]},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sufficient"] is False
    assert body["items"][0]["available"] == 0


async def test_check_availability_partial_across_multiple_products(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    sufficient_product = str(uuid.uuid4())
    insufficient_product = str(uuid.uuid4())

    await client.post(
        f"/stocks/{stock_id}/items", json={"product_id": sufficient_product, "quantity": 10}, headers=headers
    )
    await client.post(
        f"/stocks/{stock_id}/items", json={"product_id": insufficient_product, "quantity": 1}, headers=headers
    )

    resp = await client.post(
        "/stocks/check-availability",
        json={
            "items": [
                {"product_id": sufficient_product, "quantity": 5},
                {"product_id": insufficient_product, "quantity": 5},
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sufficient"] is False
    by_product = {i["product_id"]: i["sufficient"] for i in body["items"]}
    assert by_product[sufficient_product] is True
    assert by_product[insufficient_product] is False


async def test_check_availability_guest_token_allowed(client, guest_token):
    resp = await client.post(
        "/stocks/check-availability",
        json={"items": [{"product_id": str(uuid.uuid4()), "quantity": 1}]},
        headers={"x-internal-token": guest_token},
    )
    assert resp.status_code == 200


async def test_check_availability_reserved_quantity_makes_it_insufficient(client, guest_token, session):
    product_id = uuid.uuid4()
    await _make_stock_item(session, quantity=10, reserved_quantity=8, product_id=product_id)

    resp = await client.post(
        "/stocks/check-availability",
        json={"items": [{"product_id": str(product_id), "quantity": 5}]},
        headers={"x-internal-token": guest_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sufficient"] is False
    assert body["items"][0]["available"] == 2
    assert body["items"][0]["sufficient"] is False


async def test_check_availability_reserved_quantity_still_sufficient(client, guest_token, session):
    product_id = uuid.uuid4()
    await _make_stock_item(session, quantity=10, reserved_quantity=3, product_id=product_id)

    resp = await client.post(
        "/stocks/check-availability",
        json={"items": [{"product_id": str(product_id), "quantity": 5}]},
        headers={"x-internal-token": guest_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sufficient"] is True
    assert body["items"][0]["available"] == 7
    assert body["items"][0]["sufficient"] is True


async def test_check_availability_fully_reserved_is_insufficient(client, guest_token, session):
    product_id = uuid.uuid4()
    await _make_stock_item(session, quantity=6, reserved_quantity=6, product_id=product_id)

    resp = await client.post(
        "/stocks/check-availability",
        json={"items": [{"product_id": str(product_id), "quantity": 1}]},
        headers={"x-internal-token": guest_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sufficient"] is False
    assert body["items"][0]["available"] == 0
    assert body["items"][0]["sufficient"] is False
