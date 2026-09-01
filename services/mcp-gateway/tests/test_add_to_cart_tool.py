"""STR-146: proves the MCP Gateway forwards the *caller's* internal-token to
Orders unchanged for add_to_cart/get_cart/remove_from_cart, and that there is
no argument on any cart tool an LLM could use to address a different
customer's cart — ownership is resolved entirely from the forwarded token's
`sub`, by Orders' own scoping (services/orders/src/orders/routers/cart.py),
never by an id passed in the tool call."""

import httpx
import respx

from tests.conftest import mcp_session, mint_internal_token

ORDERS_URL = "http://orders.invalid"
PRODUCT_ID = "11111111-1111-1111-1111-111111111111"


@respx.mock
async def test_add_to_cart_forwards_the_calling_customers_token(app):
    caller_token = mint_internal_token("customer-alice", "customer")
    route = respx.post(f"{ORDERS_URL}/cart").mock(
        return_value=httpx.Response(201, json={"items": [{"product_id": PRODUCT_ID, "quantity": 2}]})
    )

    async with mcp_session(app, caller_token) as session:
        result = await session.call_tool("add_to_cart", {"product_id": PRODUCT_ID, "quantity": 2})

    assert result.isError is False
    assert route.called
    # The exact token presented to the Gateway is what reaches Orders — not a
    # Gateway-minted admin token — so Orders' own owner_id==claims.sub check
    # resolves against the real customer.
    assert route.calls.last.request.headers["x-internal-token"] == caller_token


@respx.mock
async def test_get_cart_forwards_the_callers_own_token_not_a_shared_identity(app):
    # Companion to the add_to_cart case above — get_cart is scoped the same
    # way, purely by the forwarded token's sub, with no id argument.
    caller_token = mint_internal_token("customer-bob", "customer")
    route = respx.get(f"{ORDERS_URL}/cart").mock(return_value=httpx.Response(200, json={"items": []}))

    async with mcp_session(app, caller_token) as session:
        await session.call_tool("get_cart", {})

    assert route.calls.last.request.headers["x-internal-token"] == caller_token


async def test_add_to_cart_has_no_customer_id_argument_to_hallucinate(app):
    # A hallucinated customer_id isn't a valid argument for the underlying
    # callable at all — the tool contract has no seam for cross-customer
    # pollution, independent of what Orders does.
    async with mcp_session(app, mint_internal_token("cust-x", "customer")) as session:
        result = await session.call_tool(
            "add_to_cart", {"product_id": PRODUCT_ID, "quantity": 2, "customer_id": "someone-elses-id"}
        )
    assert result.isError is True


async def test_add_to_cart_with_non_uuid_product_id_returns_an_actionable_error(app):
    # STR-148: the shopping agent's LLM occasionally sends a product's
    # name/description instead of its id. That must surface with a message
    # that explains the mistake (tools/orders.py's _require_uuid).
    async with mcp_session(app, mint_internal_token("cust-x", "customer")) as session:
        result = await session.call_tool("add_to_cart", {"product_id": "Aged Dutch Gouda", "quantity": 1})
    assert result.isError is True
    assert "must be a UUID" in result.content[0].text


async def test_get_cart_has_no_customer_id_argument(app):
    async with mcp_session(app, mint_internal_token("cust-x", "customer")) as session:
        result = await session.call_tool("get_cart", {"customer_id": "someone-elses-id"})
    assert result.isError is True
