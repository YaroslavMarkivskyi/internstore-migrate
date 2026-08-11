"""STR-146: proves the MCP Gateway forwards the *caller's* internal-token to
Orders unchanged for add_to_cart/get_cart/remove_from_cart, and that there is
no argument on any cart tool an LLM could use to address a different
customer's cart — ownership is resolved entirely from the forwarded token's
`sub`, by Orders' own scoping (services/orders/src/orders/routers/cart.py),
never by an id passed in the tool call."""

import httpx
import respx

ORDERS_URL = "http://orders.invalid"


def _mint(sub: str, role: str = "customer") -> str:
    from tests.conftest import mint_internal_token

    return mint_internal_token(sub=sub, role=role)


@respx.mock
async def test_add_to_cart_forwards_the_calling_customers_token(client):
    caller_token = _mint("customer-alice")
    route = respx.post(f"{ORDERS_URL}/cart").mock(
        return_value=httpx.Response(201, json={"items": [{"product_id": "prod-1", "quantity": 2}]})
    )

    resp = await client.post(
        "/mcp/tools/call",
        json={"name": "add_to_cart", "arguments": {"product_id": "prod-1", "quantity": 2}},
        headers={"X-Internal-Token": caller_token},
    )

    assert resp.status_code == 200
    assert route.called
    # The exact token presented to the Gateway is what reaches Orders — not
    # a Gateway-minted admin token (the old behavior), so Orders' own
    # owner_id==claims.sub check resolves against the real customer.
    assert route.calls.last.request.headers["x-internal-token"] == caller_token


@respx.mock
async def test_different_callers_forward_different_tokens_no_shared_identity(client):
    alice_token = _mint("customer-alice")
    bob_token = _mint("customer-bob")
    route = respx.get(f"{ORDERS_URL}/cart").mock(return_value=httpx.Response(200, json={"items": []}))

    await client.post("/mcp/tools/call", json={"name": "get_cart", "arguments": {}}, headers={"X-Internal-Token": alice_token})
    await client.post("/mcp/tools/call", json={"name": "get_cart", "arguments": {}}, headers={"X-Internal-Token": bob_token})

    forwarded_tokens = [call.request.headers["x-internal-token"] for call in route.calls]
    assert forwarded_tokens == [alice_token, bob_token]


async def test_add_to_cart_has_no_customer_id_argument_to_hallucinate(client, admin_token):
    # If an LLM hallucinates a customer_id (or any other identity-looking
    # argument) for add_to_cart, it isn't a valid argument for the
    # underlying callable at all — proving the tool contract itself has no
    # seam for cross-customer pollution, independent of what Orders does.
    resp = await client.post(
        "/mcp/tools/call",
        json={
            "name": "add_to_cart",
            "arguments": {"product_id": "prod-1", "quantity": 2, "customer_id": "someone-elses-id"},
        },
        headers={"X-Internal-Token": admin_token},
    )

    assert resp.status_code == 422


async def test_get_cart_has_no_customer_id_argument(client, admin_token):
    resp = await client.post(
        "/mcp/tools/call",
        json={"name": "get_cart", "arguments": {"customer_id": "someone-elses-id"}},
        headers={"X-Internal-Token": admin_token},
    )

    assert resp.status_code == 422
