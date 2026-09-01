"""Phase 3 — the public MCP door (nginx `/api/mcp`).

nginx does the Firebase -> internal-token exchange and adds `X-MCP-Public`;
the gateway then caps the caller at the customer tier and serves RFC 9728
discovery metadata unauthenticated.
"""

from tests.conftest import mcp_session, mint_internal_token

_PUBLIC = {"X-MCP-Public": "1"}


async def test_oauth_protected_resource_metadata_is_public_and_points_at_firebase(client):
    resp = await client.get("/.well-known/oauth-protected-resource")
    assert resp.status_code == 200
    body = resp.json()
    assert body["resource"].endswith("/api/mcp")
    assert body["authorization_servers"] == ["https://securetoken.google.com/test-project"]
    assert body["bearer_methods_supported"] == ["header"]


async def test_public_admin_token_is_capped_to_the_customer_tier(app):
    # An admin connecting from outside the mesh (their own Claude Desktop)
    # must not get the ops / telemetry / security tools.
    async with mcp_session(app, mint_internal_token("admin-1", "admin"), extra_headers=_PUBLIC) as session:
        tools = {t.name for t in (await session.list_tools()).tools}
        blocked = await session.call_tool("get_visit_log", {"warehouse_id": "w", "date_from": "a", "date_to": "b"})
    assert "get_cart" in tools and "search_products" in tools
    assert not (tools & {"get_visit_log", "get_pending_orders", "get_active_incidents", "get_active_users"})
    assert blocked.isError is True


async def test_public_customer_token_gets_the_normal_shopping_tier(app):
    async with mcp_session(app, mint_internal_token("cust-1", "customer"), extra_headers=_PUBLIC) as session:
        tools = {t.name for t in (await session.list_tools()).tools}
    assert {"get_cart", "add_to_cart", "search_products", "search_help"} <= tools


async def test_internal_admin_token_without_the_marker_still_gets_the_ops_tier(app):
    async with mcp_session(app, mint_internal_token("admin-1", "admin")) as session:
        tools = {t.name for t in (await session.list_tools()).tools}
    assert "get_visit_log" in tools
