from unittest.mock import AsyncMock

from mcp_gateway.schema import TOOL_SPECS_BY_NAME

from tests.conftest import mint_internal_token


async def test_mcp_info_requires_internal_token(client):
    resp = await client.get("/mcp")
    assert resp.status_code == 401


async def test_mcp_info_returns_server_metadata(client, admin_token):
    resp = await client.get("/mcp", headers={"X-Internal-Token": admin_token})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "internstore-mcp-gateway"
    assert "tools" in body["capabilities"]


async def test_list_tools_returns_full_catalog(client, admin_token):
    resp = await client.get("/mcp/tools", headers={"X-Internal-Token": admin_token})
    assert resp.status_code == 200
    names = {tool["name"] for tool in resp.json()["tools"]}
    assert names == set(TOOL_SPECS_BY_NAME.keys())


async def test_call_tool_requires_internal_token(client):
    resp = await client.post("/mcp/tools/call", json={"name": "get_order_status", "arguments": {"order_id": "x"}})
    assert resp.status_code == 401


async def test_call_tool_routes_to_registry(app, client, admin_token):
    app.state.tool_registry["get_order_status"] = AsyncMock(return_value={"id": "order-1", "status": "paid"})

    resp = await client.post(
        "/mcp/tools/call",
        json={"name": "get_order_status", "arguments": {"order_id": "order-1"}},
        headers={"X-Internal-Token": admin_token},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "get_order_status"
    assert body["result"] == {"id": "order-1", "status": "paid"}


async def test_call_tool_unknown_name_returns_404(client, admin_token):
    resp = await client.post(
        "/mcp/tools/call",
        json={"name": "not_a_real_tool", "arguments": {}},
        headers={"X-Internal-Token": admin_token},
    )
    assert resp.status_code == 404


async def test_call_tool_invalid_arguments_returns_422(app, client, admin_token):
    async def _requires_order_id(order_id: str) -> dict:
        return {"order_id": order_id}

    app.state.tool_registry["get_order_status"] = _requires_order_id

    resp = await client.post(
        "/mcp/tools/call",
        json={"name": "get_order_status", "arguments": {"wrong_arg": "x"}},
        headers={"X-Internal-Token": admin_token},
    )
    assert resp.status_code == 422


async def test_sse_stream_requires_internal_token(client):
    resp = await client.get("/mcp/sse")
    assert resp.status_code == 401


async def test_sse_stream_emits_endpoint_event(client, admin_token):
    async with client.stream("GET", "/mcp/sse", headers={"X-Internal-Token": admin_token}) as resp:
        assert resp.status_code == 200
        body = b""
        async for chunk in resp.aiter_bytes():
            body += chunk
        assert b"event: endpoint" in body
