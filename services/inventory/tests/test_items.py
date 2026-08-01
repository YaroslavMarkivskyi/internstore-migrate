import uuid

from tests.conftest import create_stock


async def test_list_items_consolidates_across_stocks(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_a = await create_stock(client, admin_token, name="Stock A")
    stock_b = await create_stock(client, admin_token, name="Stock B")
    product_id = str(uuid.uuid4())

    await client.post(f"/stocks/{stock_a}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)
    await client.post(f"/stocks/{stock_b}/items", json={"product_id": product_id, "quantity": 7}, headers=headers)

    resp = await client.get("/items")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["product_id"] == product_id
    assert body[0]["quantity"] == 12


async def test_list_items_filter_by_stock_id(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_a = await create_stock(client, admin_token, name="Stock A")
    stock_b = await create_stock(client, admin_token, name="Stock B")
    product_a = str(uuid.uuid4())
    product_b = str(uuid.uuid4())

    await client.post(f"/stocks/{stock_a}/items", json={"product_id": product_a, "quantity": 5}, headers=headers)
    await client.post(f"/stocks/{stock_b}/items", json={"product_id": product_b, "quantity": 7}, headers=headers)

    resp = await client.get("/items", params={"stock_id": stock_a})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["product_id"] == product_a


async def test_list_items_filter_by_quantity_range(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    low = str(uuid.uuid4())
    high = str(uuid.uuid4())

    await client.post(f"/stocks/{stock_id}/items", json={"product_id": low, "quantity": 2}, headers=headers)
    await client.post(f"/stocks/{stock_id}/items", json={"product_id": high, "quantity": 20}, headers=headers)

    resp = await client.get("/items", params={"min_quantity": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert [i["product_id"] for i in body] == [high]

    resp = await client.get("/items", params={"max_quantity": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert [i["product_id"] for i in body] == [low]
