import httpx
import pytest
import respx

from ai_assistant.mcp_client import MCPGatewayClient

BASE_URL = "http://mcp-gateway.invalid"


def _client() -> MCPGatewayClient:
    return MCPGatewayClient(BASE_URL, timeout_seconds=5.0)


@respx.mock
async def test_call_tool_returns_result_on_success():
    respx.post(f"{BASE_URL}/mcp/tools/call").mock(
        return_value=httpx.Response(200, json={"name": "get_cart", "result": {"items": []}})
    )

    result = await _client().call_tool("token", "get_cart", {})

    assert result == {"items": []}


@respx.mock
async def test_call_tool_error_surfaces_the_gateways_detail_message():
    """STR-148: found live — plain resp.raise_for_status() flattens a 422's
    actual `detail` (e.g. "product_id must be a UUID...") into a generic
    "Client error '422 Unprocessable Entity' for url '...'", which the
    ReAct loop feeds straight back to the model as the tool error. A
    message with no specifics gives the model nothing to correct — it just
    gives up instead of retrying with a fixed argument."""
    respx.post(f"{BASE_URL}/mcp/tools/call").mock(
        return_value=httpx.Response(422, json={"detail": "product_id must be a UUID from a previous result"})
    )

    with pytest.raises(httpx.HTTPStatusError, match="product_id must be a UUID"):
        await _client().call_tool("token", "add_to_cart", {"product_id": "not-a-uuid", "quantity": 1})


@respx.mock
async def test_call_tool_error_falls_back_gracefully_with_no_json_body():
    respx.post(f"{BASE_URL}/mcp/tools/call").mock(return_value=httpx.Response(500, text="upstream exploded"))

    with pytest.raises(httpx.HTTPStatusError, match="500"):
        await _client().call_tool("token", "get_cart", {})
