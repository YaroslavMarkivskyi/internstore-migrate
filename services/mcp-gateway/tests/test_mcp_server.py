"""Phase 1: the real MCP protocol surface at /mcp/stream — a genuine
JSON-RPC / Streamable HTTP server driven here by the real `mcp` client over an
in-process ASGI transport."""

from contextlib import asynccontextmanager

import pytest
from httpx2 import ASGITransport, AsyncClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError

from mcp_gateway.schema import TOOL_SPECS_BY_NAME
from tests.conftest import mint_internal_token


@asynccontextmanager
async def _mcp_session(app, token: str | None):
    headers = {"X-Internal-Token": token} if token else {}
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as http,
        streamable_http_client("http://test/mcp/stream", http_client=http) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


def _flatten(exc: BaseException) -> list[BaseException]:
    if isinstance(exc, BaseExceptionGroup):
        return [sub for e in exc.exceptions for sub in _flatten(e)]
    return [exc]


async def test_list_tools_matches_the_schema_catalog(app):
    async with _mcp_session(app, mint_internal_token("ai-assistant", "assistant")) as session:
        result = await session.list_tools()
    assert {t.name for t in result.tools} == set(TOOL_SPECS_BY_NAME)
    order_status = next(t for t in result.tools if t.name == "get_order_status")
    assert order_status.input_schema == TOOL_SPECS_BY_NAME["get_order_status"]["input_schema"]


async def test_call_tool_routes_to_the_registry_and_forwards_identity(app):
    captured: dict = {}

    async def _fake_get_order_status(*, token: str, order_id: str) -> dict:
        captured["token"] = token
        captured["order_id"] = order_id
        return {"id": order_id, "status": "paid"}

    app.state.tool_registry["get_order_status"] = _fake_get_order_status
    token = mint_internal_token("cust-1", "customer")

    async with _mcp_session(app, token) as session:
        result = await session.call_tool("get_order_status", {"order_id": "order-1"})

    assert result.is_error is False
    assert result.structured_content == {"id": "order-1", "status": "paid"}
    assert captured == {"token": token, "order_id": "order-1"}


async def test_unknown_tool_comes_back_as_an_error_result(app):
    async with _mcp_session(app, mint_internal_token("ai-assistant", "assistant")) as session:
        result = await session.call_tool("not_a_real_tool", {})
    assert result.is_error is True
    assert "not_a_real_tool" in result.content[0].text


async def test_bad_arguments_come_back_as_an_error_result(app):
    async def _requires_order_id(*, token: str, order_id: str) -> dict:
        return {"order_id": order_id}

    app.state.tool_registry["get_order_status"] = _requires_order_id
    async with _mcp_session(app, mint_internal_token("ai-assistant", "assistant")) as session:
        result = await session.call_tool("get_order_status", {"wrong_arg": "x"})
    assert result.is_error is True
    assert "get_order_status" in result.content[0].text


async def test_missing_internal_token_is_rejected(app):
    # The server rejects the unauthenticated tools/list as a JSON-RPC error;
    # the client surfaces it (directly or wrapped in the transport task
    # group's ExceptionGroup).
    with pytest.raises((MCPError, BaseExceptionGroup)) as excinfo:
        async with _mcp_session(app, None) as session:
            await session.list_tools()
    assert any(isinstance(e, MCPError) and "internal token" in str(e) for e in _flatten(excinfo.value))


async def test_checkout_is_structurally_absent(app):
    async with _mcp_session(app, mint_internal_token("ai-assistant", "assistant")) as session:
        result = await session.list_tools()
    assert not [t for t in result.tools if "checkout" in t.name or "payment" in t.name]
