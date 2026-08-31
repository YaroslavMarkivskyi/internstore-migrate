from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
import respx

from mcp_gateway.tools.orders import OrdersToolsClient

BASE_URL = "http://orders.invalid"
PRODUCT_ID = "11111111-1111-1111-1111-111111111111"


def _client() -> OrdersToolsClient:
    return OrdersToolsClient(BASE_URL, timeout_seconds=5.0)


class _FakeSession:
    """Stands in for an AsyncSession over the mirrored product_embeddings
    table — yields the given rows from execute()."""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def execute(self, _stmt: object) -> object:
        return iter(self._rows)


def _priced_client(rows: list) -> OrdersToolsClient:
    return OrdersToolsClient(BASE_URL, timeout_seconds=5.0, session_factory=lambda: _FakeSession(rows))


_GOUDA_ROW = SimpleNamespace(
    product_id=PRODUCT_ID, name="Aged Gouda", price=12.5
)


@respx.mock
async def test_get_order_status_calls_admin_endpoint_with_internal_token():
    route = respx.get(f"{BASE_URL}/admin/order-1").mock(
        return_value=httpx.Response(200, json={"id": "order-1", "status": "paid", "items": []})
    )

    result = await _client().get_order_status("caller-token", "order-1")

    assert route.called
    assert route.calls.last.request.headers["x-internal-token"] == "caller-token"
    assert result["status"] == "paid"


@respx.mock
async def test_list_customer_orders_passes_owner_id_and_applies_limit():
    orders = [{"id": f"order-{i}", "status": "new", "created_at": "2026-08-01T00:00:00Z", "items": []} for i in range(10)]
    route = respx.get(f"{BASE_URL}/admin", params={"owner_id": "customer-1"}).mock(
        return_value=httpx.Response(200, json=orders)
    )

    result = await _client().list_customer_orders("caller-token", "customer-1", limit=3)

    assert route.called
    assert len(result) == 3


@respx.mock
async def test_get_my_orders_hits_customer_endpoint_forwards_token_and_limits():
    orders = [{"id": f"o-{i}", "status": "paid", "created_at": "2026-08-01T00:00:00Z", "items": []} for i in range(10)]
    route = respx.get(f"{BASE_URL}/orders").mock(return_value=httpx.Response(200, json=orders))

    result = await _client().get_my_orders("customer-token", limit=3)

    assert route.called
    # No owner_id/customer_id param — Orders scopes to the forwarded token's sub.
    assert "owner_id" not in route.calls.last.request.url.params
    assert route.calls.last.request.headers["x-internal-token"] == "customer-token"
    assert len(result) == 3


@respx.mock
async def test_get_my_order_hits_customer_endpoint_by_id():
    route = respx.get(f"{BASE_URL}/orders/order-1").mock(
        return_value=httpx.Response(200, json={"id": "order-1", "status": "shipped", "items": []})
    )

    result = await _client().get_my_order("customer-token", "order-1")

    assert route.called
    assert route.calls.last.request.headers["x-internal-token"] == "customer-token"
    assert result["status"] == "shipped"


@respx.mock
async def test_get_my_order_propagates_404_for_someone_elses_order():
    respx.get(f"{BASE_URL}/orders/not-mine").mock(return_value=httpx.Response(404, json={"detail": "Order not found"}))

    with pytest.raises(httpx.HTTPStatusError):
        await _client().get_my_order("customer-token", "not-mine")


@respx.mock
async def test_get_pending_orders_filters_status_and_age():
    now = datetime.now(timezone.utc)
    old_pending = {"id": "old", "status": "pending", "created_at": (now - timedelta(minutes=120)).isoformat()}
    recent_pending = {"id": "recent", "status": "pending", "created_at": (now - timedelta(minutes=5)).isoformat()}
    paid = {"id": "paid", "status": "paid", "created_at": (now - timedelta(minutes=120)).isoformat()}
    respx.get(f"{BASE_URL}/admin").mock(
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
async def test_get_cart_forwards_caller_token_and_enriches_with_prices():
    route = respx.get(f"{BASE_URL}/cart").mock(
        return_value=httpx.Response(200, json={"items": [{"product_id": PRODUCT_ID, "quantity": 2}]})
    )

    result = await _priced_client([_GOUDA_ROW]).get_cart("customer-alices-token")

    assert route.called
    assert route.calls.last.request.headers["x-internal-token"] == "customer-alices-token"
    assert result == {
        "items": [
            {
                "product_id": PRODUCT_ID,
                "name": "Aged Gouda",
                "quantity": 2,
                "unit_price": 12.5,
                "line_total": 25.0,
            }
        ],
        "total": 25.0,
    }


@respx.mock
async def test_get_cart_without_a_session_factory_returns_quantities_but_no_prices():
    respx.get(f"{BASE_URL}/cart").mock(
        return_value=httpx.Response(200, json={"items": [{"product_id": PRODUCT_ID, "quantity": 2}]})
    )

    result = await _client().get_cart("customer-alices-token")

    assert result == {
        "items": [
            {
                "product_id": PRODUCT_ID,
                "name": None,
                "quantity": 2,
                "unit_price": None,
                "line_total": None,
            }
        ],
        "total": None,
    }


@respx.mock
async def test_add_to_cart_forwards_caller_token_and_body_and_returns_the_enriched_cart():
    route = respx.post(f"{BASE_URL}/cart").mock(
        return_value=httpx.Response(201, json={"items": [{"product_id": PRODUCT_ID, "quantity": 2}]})
    )

    result = await _priced_client([_GOUDA_ROW]).add_to_cart("customer-alices-token", PRODUCT_ID, 2)

    assert route.called
    assert route.calls.last.request.headers["x-internal-token"] == "customer-alices-token"
    sent_body = route.calls.last.request.content
    assert PRODUCT_ID.encode() in sent_body and b'"quantity":2' in sent_body
    assert result["total"] == 25.0
    assert result["items"][0]["name"] == "Aged Gouda"


@respx.mock
async def test_remove_from_cart_forwards_caller_token_and_rereads_the_cart():
    delete_route = respx.delete(f"{BASE_URL}/cart/items/{PRODUCT_ID}").mock(return_value=httpx.Response(204))
    get_route = respx.get(f"{BASE_URL}/cart").mock(return_value=httpx.Response(200, json={"items": []}))

    result = await _client().remove_from_cart("customer-alices-token", PRODUCT_ID)

    assert delete_route.called and get_route.called
    assert delete_route.calls.last.request.headers["x-internal-token"] == "customer-alices-token"
    assert result == {"items": [], "total": None}


# --- STR-148: found live — the shopping agent's LLM occasionally passes a
# product's name/description text instead of the product_id a prior
# search_products/get_cart result actually returned. Failing fast here
# (before ever reaching Orders) with a message that explains what's wrong
# gives the ReAct loop something actionable to retry with, instead of a
# generic 500 with no useful detail.


@respx.mock
async def test_add_to_cart_rejects_a_non_uuid_product_id():
    route = respx.post(f"{BASE_URL}/cart")

    with pytest.raises(ValueError, match="must be a UUID"):
        await _client().add_to_cart("customer-alices-token", "Aged Dutch Gouda", 1)

    assert not route.called  # never even reaches Orders


@respx.mock
async def test_remove_from_cart_rejects_a_non_uuid_product_id():
    route = respx.delete(f"{BASE_URL}/cart/items/not-a-uuid")

    with pytest.raises(ValueError, match="must be a UUID"):
        await _client().remove_from_cart("customer-alices-token", "not-a-uuid")

    assert not route.called


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
