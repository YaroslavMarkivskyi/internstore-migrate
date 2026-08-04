from unittest.mock import AsyncMock

import pytest

from mcp_gateway.router import (
    GatewayClients,
    ToolNotFoundError,
    build_tool_registry,
    call_tool,
)
from mcp_gateway.schema import TOOL_SPECS_BY_NAME


def _fake_clients() -> GatewayClients:
    return GatewayClients(
        orders=AsyncMock(),
        inventory=AsyncMock(),
        catalog=AsyncMock(),
        product_search=AsyncMock(),
        telemetry=AsyncMock(),
        security=AsyncMock(),
        chat=AsyncMock(),
    )


def test_every_tool_spec_has_a_registered_callable():
    registry = build_tool_registry(_fake_clients())
    assert set(registry.keys()) == set(TOOL_SPECS_BY_NAME.keys())


async def test_call_tool_routes_to_matching_callable():
    clients = _fake_clients()
    clients.orders.get_order_status = AsyncMock(return_value={"id": "order-1", "status": "paid"})
    registry = build_tool_registry(clients)

    result = await call_tool(registry, "get_order_status", {"order_id": "order-1"})

    assert result == {"id": "order-1", "status": "paid"}
    clients.orders.get_order_status.assert_awaited_once_with(order_id="order-1")


async def test_call_tool_unknown_name_raises():
    registry = build_tool_registry(_fake_clients())
    with pytest.raises(ToolNotFoundError):
        await call_tool(registry, "not_a_real_tool", {})
