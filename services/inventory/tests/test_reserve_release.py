import uuid

from inventory import commands
from inventory.event_store import ConcurrencyConflict
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


# STR-160b: STR-159b's live 30-way-concurrent test against a real cluster
# found that exhausted retries surfaced as an uncaught 500 -- forcing that
# outcome with genuine concurrency in a unit test would be flaky (it needs
# ~30 truly-parallel requests to reliably race), so this forces the same
# exhaustion deterministically via monkeypatch instead, same technique as
# test_event_append.py's test_run_with_retry_raises_after_exhausting_attempts
# (which already covers this at the commands.py level) -- this test is the
# HTTP-boundary half: does the router turn that same exception into a
# handled response instead of leaking it as an unhandled 500.
async def test_reserve_stock_returns_409_when_retries_are_exhausted(client, admin_token, monkeypatch):
    headers = {"x-internal-token": admin_token}
    stock_id = await create_stock(client, admin_token)
    product_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())
    await client.post(f"/stocks/{stock_id}/items", json={"product_id": product_id, "quantity": 5}, headers=headers)

    async def always_conflicts(*args, **kwargs):
        raise ConcurrencyConflict("exhausted retries")

    monkeypatch.setattr(commands, "run_with_retry", always_conflicts)

    resp = await client.post(
        "/stocks/reserve",
        json={"order_id": order_id, "items": [{"product_id": product_id, "quantity": 1}]},
        headers=headers,
    )

    assert resp.status_code == 409
    # Actionable, not a generic/opaque server error -- a caller (or
    # checkout-workflow's ReserveStock activity logs) can tell this was a
    # contention conflict for this specific order, not an unrelated fault.
    assert order_id in resp.json()["detail"]
    assert "retry" in resp.json()["detail"].lower()


async def test_release_stock_returns_409_when_retries_are_exhausted(client, admin_token, monkeypatch):
    headers = {"x-internal-token": admin_token}
    order_id = str(uuid.uuid4())

    async def always_conflicts(*args, **kwargs):
        raise ConcurrencyConflict("exhausted retries")

    monkeypatch.setattr(commands, "run_with_retry", always_conflicts)

    resp = await client.post("/stocks/release", json={"order_id": order_id}, headers=headers)

    assert resp.status_code == 409
    assert order_id in resp.json()["detail"]
    assert "retry" in resp.json()["detail"].lower()
