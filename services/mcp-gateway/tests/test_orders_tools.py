from datetime import datetime, timedelta, timezone

import httpx
import respx

from mcp_gateway.tools.orders import OrdersToolsClient

BASE_URL = "http://orders.invalid"


def _client() -> OrdersToolsClient:
    return OrdersToolsClient(BASE_URL, timeout_seconds=5.0)


@respx.mock
async def test_get_order_status_calls_admin_endpoint_with_internal_token():
    route = respx.get(f"{BASE_URL}/orders/admin/order-1").mock(
        return_value=httpx.Response(200, json={"id": "order-1", "status": "paid", "items": []})
    )

    result = await _client().get_order_status("caller-token", "order-1")

    assert route.called
    assert route.calls.last.request.headers["x-internal-token"] == "caller-token"
    assert result["status"] == "paid"


@respx.mock
async def test_list_customer_orders_passes_owner_id_and_applies_limit():
    orders = [{"id": f"order-{i}", "status": "new", "created_at": "2026-08-01T00:00:00Z", "items": []} for i in range(10)]
    route = respx.get(f"{BASE_URL}/orders/admin", params={"owner_id": "customer-1"}).mock(
        return_value=httpx.Response(200, json=orders)
    )

    result = await _client().list_customer_orders("caller-token", "customer-1", limit=3)

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

    result = await _client().get_pending_orders("caller-token", older_than_minutes=60)

    assert [order["id"] for order in result] == ["old"]


# --- STR-146: cart write-tools. The interesting property isn't just "the
# HTTP call happens" — it's that the *caller's* token is what goes out on
# the wire, unchanged, since that's what makes Orders' own owner_id==sub
# scoping the real authorization boundary (see
# services/orders/src/orders/routers/cart.py) instead of something the
# Gateway has to duplicate.


@respx.mock
async def test_get_cart_forwards_caller_token():
    route = respx.get(f"{BASE_URL}/cart").mock(
        return_value=httpx.Response(200, json={"items": [{"product_id": "prod-1", "quantity": 2}]})
    )

    result = await _client().get_cart("customer-alices-token")

    assert route.called
    assert route.calls.last.request.headers["x-internal-token"] == "customer-alices-token"
    assert result == {"items": [{"product_id": "prod-1", "quantity": 2}]}


@respx.mock
async def test_add_to_cart_forwards_caller_token_and_body():
    route = respx.post(f"{BASE_URL}/cart").mock(
        return_value=httpx.Response(201, json={"items": [{"product_id": "prod-1", "quantity": 2}]})
    )

    result = await _client().add_to_cart("customer-alices-token", "prod-1", 2)

    assert route.called
    assert route.calls.last.request.headers["x-internal-token"] == "customer-alices-token"
    sent_body = route.calls.last.request.content
    assert b"prod-1" in sent_body and b'"quantity":2' in sent_body
    assert result == {"items": [{"product_id": "prod-1", "quantity": 2}]}


@respx.mock
async def test_remove_from_cart_forwards_caller_token():
    route = respx.delete(f"{BASE_URL}/cart/items/prod-1").mock(return_value=httpx.Response(204))

    result = await _client().remove_from_cart("customer-alices-token", "prod-1")

    assert route.called
    assert route.calls.last.request.headers["x-internal-token"] == "customer-alices-token"
    assert result == {"removed_product_id": "prod-1"}


@respx.mock
async def test_cart_tools_never_mint_their_own_token_a_wrong_customer_id_cannot_smuggle_ownership():
    # There is no customer_id parameter on any cart tool (see schema.py) —
    # even if the LLM hallucinated one, add_to_cart's signature has nowhere
    # to put it. Whichever token is forwarded is whose cart is touched;
    # Orders' owner_id==claims.sub scoping (not this client) is what
    # actually enforces that. This test documents that the Gateway-side
    # contract has no seam for a spoofed customer id, full stop.
    import inspect

    from mcp_gateway.tools.orders import OrdersToolsClient as _Client

    for method_name in ("get_cart", "add_to_cart", "remove_from_cart"):
        params = inspect.signature(getattr(_Client, method_name)).parameters
        assert "customer_id" not in params
