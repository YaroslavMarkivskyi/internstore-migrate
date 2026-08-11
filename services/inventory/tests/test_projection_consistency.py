"""The core correctness property of event sourcing: after any sequence of
commands, the live `stock_items` projection must exactly match a
from-scratch replay of that aggregate's `stock_events` stream. This is
what actually proves the projection is trustworthy -- everything else
(history/as-of/snapshots) is built on the assumption this holds."""

import uuid

from sqlalchemy import select

from inventory.event_store import load_stream
from inventory.events import compute_aggregate_id
from inventory.models import StockItem
from inventory.projector import replay
from tests.conftest import create_stock


async def _assert_projection_matches_replay(client, stock_id: str, product_id: str) -> None:
    aggregate_id = compute_aggregate_id(uuid.UUID(stock_id), uuid.UUID(product_id))
    async with client.app.state.session_factory() as session:
        stream = await load_stream(session, aggregate_id)
        replayed = replay(stream)

        result = await session.execute(
            select(StockItem).where(StockItem.stock_id == uuid.UUID(stock_id), StockItem.product_id == uuid.UUID(product_id))
        )
        live = result.scalar_one_or_none()

    if not replayed["exists"]:
        assert live is None
        return

    assert live is not None
    assert live.quantity == replayed["quantity"]
    assert live.reserved_quantity == replayed["reserved_quantity"]
    assert live.is_unavailable == replayed["is_unavailable"]


async def test_projection_matches_replay_across_a_mixed_command_sequence(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_a = await create_stock(client, admin_token, name="Warehouse A")
    stock_b = await create_stock(client, admin_token, name="Warehouse B")
    product_id = str(uuid.uuid4())

    # StockItemCreated
    resp = await client.post(f"/stocks/{stock_a}/items", json={"product_id": product_id, "quantity": 20}, headers=headers)
    item_id = resp.json()["id"]
    await _assert_projection_matches_replay(client, stock_a, product_id)

    # ItemReceived
    await client.post(f"/stocks/{stock_a}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)
    await _assert_projection_matches_replay(client, stock_a, product_id)

    # ItemMovedOut / ItemMovedIn -- two aggregates in one command
    await client.post(
        f"/stocks/{stock_a}/items/{item_id}/move", json={"to_stock_id": stock_b, "quantity": 10}, headers=headers
    )
    await _assert_projection_matches_replay(client, stock_a, product_id)
    await _assert_projection_matches_replay(client, stock_b, product_id)

    # StockReserved (via the Temporal-facing reserve endpoint)
    order_id = str(uuid.uuid4())
    await client.post(
        "/stocks/reserve", json={"order_id": order_id, "items": [{"product_id": product_id, "quantity": 3}]}, headers=headers
    )
    await _assert_projection_matches_replay(client, stock_a, product_id)
    await _assert_projection_matches_replay(client, stock_b, product_id)

    # StockReleased
    await client.post("/stocks/release", json={"order_id": order_id}, headers=headers)
    await _assert_projection_matches_replay(client, stock_a, product_id)
    await _assert_projection_matches_replay(client, stock_b, product_id)

    # StockItemQuantitySet
    await client.patch(f"/stocks/{stock_a}/items/{item_id}", json={"quantity": 42}, headers=headers)
    await _assert_projection_matches_replay(client, stock_a, product_id)

    # MarkedUnavailable / MarkedAvailable
    resp = await client.get(f"/stocks/{stock_a}/items", headers=headers)
    a_item_id = next(i["id"] for i in resp.json() if i["product_id"] == product_id)
    await client.post(f"/stocks/{stock_a}/items/{a_item_id}/mark-available", headers=headers)
    await _assert_projection_matches_replay(client, stock_a, product_id)

    # StockItemRemoved on stock_b's side (reserved_quantity is 0 there)
    resp = await client.get(f"/stocks/{stock_b}/items", headers=headers)
    b_item_id = next(i["id"] for i in resp.json() if i["product_id"] == product_id)
    await client.delete(f"/stocks/{stock_b}/items/{b_item_id}", headers=headers)
    await _assert_projection_matches_replay(client, stock_b, product_id)


async def test_projection_matches_replay_when_receive_reopens_a_removed_aggregate(client, admin_token):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())

    resp = await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)
    item_id = resp.json()["id"]
    await client.delete(f"/stocks/{stock_id}/items/{item_id}", headers=headers)
    await _assert_projection_matches_replay(client, stock_id, product_id)

    # Same (stock_id, product_id) -- reopens the same aggregate stream.
    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 7}, headers=headers)
    await _assert_projection_matches_replay(client, stock_id, product_id)
