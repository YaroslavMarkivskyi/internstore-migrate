import uuid

from tests.conftest import create_stock


async def test_history_requires_admin(client, customer_token):
    resp = await client.get(
        f"/stocks/{uuid.uuid4()}/{uuid.uuid4()}/history",
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


async def test_history_shows_exact_event_sequence(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())

    resp = await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 10}, headers=headers)
    item_id = resp.json()["id"]
    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)
    await client.patch(f"/stocks/{stock_id}/items/{item_id}", json={"quantity": 20}, headers=headers)

    resp = await client.get(f"/stocks/{stock_id}/{product_id}/history", headers=headers)
    assert resp.status_code == 200
    body = resp.json()

    event_types = [item["event_type"] for item in body["items"]]
    assert event_types == ["StockItemCreated", "ItemReceived", "StockItemQuantitySet"]
    sequence_numbers = [item["sequence_number"] for item in body["items"]]
    assert sequence_numbers == [1, 2, 3]
    assert body["items"][0]["payload"]["initial_quantity"] == 10
    assert body["items"][1]["payload"]["quantity_delta"] == 5
    assert body["items"][2]["payload"]["quantity"] == 20
    assert body["next_cursor"] is None


async def test_history_paginates_with_cursor(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())

    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 1}, headers=headers)
    for _ in range(4):
        await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 1}, headers=headers)

    first_page = await client.get(f"/stocks/{stock_id}/{product_id}/history?limit=2", headers=headers)
    assert [item["sequence_number"] for item in first_page.json()["items"]] == [1, 2]
    next_cursor = first_page.json()["next_cursor"]
    assert next_cursor == 2

    second_page = await client.get(f"/stocks/{stock_id}/{product_id}/history?limit=2&cursor={next_cursor}", headers=headers)
    assert [item["sequence_number"] for item in second_page.json()["items"]] == [3, 4]

    third_page = await client.get(
        f"/stocks/{stock_id}/{product_id}/history?limit=2&cursor={second_page.json()['next_cursor']}", headers=headers
    )
    assert [item["sequence_number"] for item in third_page.json()["items"]] == [5]
    assert third_page.json()["next_cursor"] is None


async def test_history_for_unknown_aggregate_is_an_empty_page(client, admin_token):
    headers = {"x-internal-token": admin_token}
    resp = await client.get(f"/stocks/{uuid.uuid4()}/{uuid.uuid4()}/history", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "next_cursor": None}
