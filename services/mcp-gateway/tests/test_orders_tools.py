from datetime import datetime, timedelta, timezone

import httpx
import respx

from mcp_gateway.tools.orders import OrdersToolsClient

BASE_URL = "http://orders.invalid"


def _client() -> OrdersToolsClient:
    return OrdersToolsClient(BASE_URL, timeout_seconds=5.0, internal_token_secret="test-secret")


@respx.mock
async def test_get_order_status_calls_admin_endpoint_with_internal_token():
    route = respx.get(f"{BASE_URL}/orders/admin/order-1").mock(
        return_value=httpx.Response(200, json={"id": "order-1", "status": "paid", "items": []})
    )

    result = await _client().get_order_status("order-1")

    assert route.called
    assert route.calls.last.request.headers["x-internal-token"]
    assert result["status"] == "paid"


@respx.mock
async def test_list_customer_orders_passes_owner_id_and_applies_limit():
    orders = [{"id": f"order-{i}", "status": "new", "created_at": "2026-08-01T00:00:00Z", "items": []} for i in range(10)]
    route = respx.get(f"{BASE_URL}/orders/admin", params={"owner_id": "customer-1"}).mock(
        return_value=httpx.Response(200, json=orders)
    )

    result = await _client().list_customer_orders("customer-1", limit=3)

    assert route.called
    assert len(result) == 3


@respx.mock
async def test_get_pending_orders_filters_status_and_age():
    now = datetime.now(timezone.utc)
    old_pending = {"id": "old", "status": "pending", "created_at": (now - timedelta(minutes=120)).isoformat()}
    recent_pending = {"id": "recent", "status": "pending", "created_at": (now - timedelta(minutes=5)).isoformat()}
    paid = {"id": "paid", "status": "paid", "created_at": (now - timedelta(minutes=120)).isoformat()}
    respx.get(f"{BASE_URL}/orders/admin").mock(
        return_value=httpx.Response(200, json=[old_pending, recent_pending, paid])
    )

    result = await _client().get_pending_orders(older_than_minutes=60)

    assert [order["id"] for order in result] == ["old"]
