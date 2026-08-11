import uuid
from datetime import datetime, timedelta, timezone

from tests.conftest import create_stock


async def test_as_of_requires_admin(client, customer_token):
    resp = await client.get(
        f"/stocks/{uuid.uuid4()}/{uuid.uuid4()}/as-of",
        params={"timestamp": datetime.now(timezone.utc).isoformat()},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


async def test_as_of_before_the_aggregate_existed_is_404(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())

    before = datetime.now(timezone.utc) - timedelta(hours=1)
    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)

    resp = await client.get(
        f"/stocks/{stock_id}/{product_id}/as-of", params={"timestamp": before.isoformat()}, headers=headers
    )
    assert resp.status_code == 404


async def test_as_of_at_an_intermediate_point_reconstructs_intermediate_state(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())

    resp = await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 10}, headers=headers)
    item_id = resp.json()["id"]

    midpoint = datetime.now(timezone.utc)

    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 15}, headers=headers)

    order_id = str(uuid.uuid4())
    await client.post(
        "/stocks/reserve", json={"order_id": order_id, "items": [{"product_id": product_id, "quantity": 3}]}, headers=headers
    )

    # At the midpoint: only the initial receive had happened.
    resp = await client.get(
        f"/stocks/{stock_id}/{product_id}/as-of", params={"timestamp": midpoint.isoformat()}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["quantity"] == 10
    assert body["reserved_quantity"] == 0

    # Now (unbounded timestamp): reflects the later receive and reservation.
    now = datetime.now(timezone.utc)
    resp = await client.get(f"/stocks/{stock_id}/{product_id}/as-of", params={"timestamp": now.isoformat()}, headers=headers)
    body = resp.json()
    assert body["quantity"] == 25
    assert body["reserved_quantity"] == 3

    # Sanity check against the live list endpoint.
    live = await client.get(f"/stocks/{stock_id}/items", headers=headers)
    live_item = next(i for i in live.json() if i["id"] == item_id)
    assert live_item["quantity"] == 25


async def test_as_of_after_removal_is_404(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())

    resp = await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)
    item_id = resp.json()["id"]
    await client.delete(f"/stocks/{stock_id}/items/{item_id}", headers=headers)

    now = datetime.now(timezone.utc)
    resp = await client.get(f"/stocks/{stock_id}/{product_id}/as-of", params={"timestamp": now.isoformat()}, headers=headers)
    assert resp.status_code == 404
