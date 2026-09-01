"""The MCP protocol surface at /mcp — driven here by the real `mcp` client
over an in-process ASGI transport."""

import pytest
from mcp.shared.exceptions import McpError

from mcp_gateway.schema import TOOL_SPECS_BY_NAME
from tests.conftest import mcp_session, mint_internal_token


def _flatten(exc: BaseException) -> list[BaseException]:
    if isinstance(exc, BaseExceptionGroup):
        return [sub for e in exc.exceptions for sub in _flatten(e)]
    return [exc]


async def test_list_tools_matches_the_schema_catalog(app):
    async with mcp_session(app, mint_internal_token("ai-assistant", "assistant")) as session:
        result = await session.list_tools()
    assert {t.name for t in result.tools} == set(TOOL_SPECS_BY_NAME)
    order_status = next(t for t in result.tools if t.name == "get_order_status")
    assert order_status.inputSchema == TOOL_SPECS_BY_NAME["get_order_status"]["input_schema"]


async def test_call_tool_routes_to_the_registry_and_forwards_identity(app):
    captured: dict = {}

    async def _fake_get_order_status(*, token: str, order_id: str) -> dict:
        captured["token"] = token
        captured["order_id"] = order_id
        return {"id": order_id, "status": "paid"}

    app.state.tool_registry["get_order_status"] = _fake_get_order_status
    token = mint_internal_token("cust-1", "customer")

    async with mcp_session(app, token) as session:
        result = await session.call_tool("get_order_status", {"order_id": "order-1"})

    assert result.isError is False
    assert result.structuredContent == {"id": "order-1", "status": "paid"}
    assert captured == {"token": token, "order_id": "order-1"}


async def test_unknown_tool_comes_back_as_an_error_result(app):
    async with mcp_session(app, mint_internal_token("ai-assistant", "assistant")) as session:
        result = await session.call_tool("not_a_real_tool", {})
    assert result.isError is True
    assert "not_a_real_tool" in result.content[0].text


async def test_bad_arguments_come_back_as_an_error_result(app):
    async def _requires_order_id(*, token: str, order_id: str) -> dict:
        return {"order_id": order_id}

    app.state.tool_registry["get_order_status"] = _requires_order_id
    async with mcp_session(app, mint_internal_token("ai-assistant", "assistant")) as session:
        result = await session.call_tool("get_order_status", {"wrong_arg": "x"})
    assert result.isError is True
    assert "get_order_status" in result.content[0].text


async def test_missing_internal_token_is_rejected(app):
    with pytest.raises((McpError, BaseExceptionGroup)) as excinfo:
        async with mcp_session(app, None) as session:
            await session.list_tools()
    assert any(isinstance(e, McpError) and "internal token" in str(e) for e in _flatten(excinfo.value))


async def test_checkout_is_structurally_absent(app):
    async with mcp_session(app, mint_internal_token("ai-assistant", "assistant")) as session:
        result = await session.list_tools()
    assert not [t for t in result.tools if "checkout" in t.name or "payment" in t.name]
