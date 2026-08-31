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
        help_search=AsyncMock(),
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

    result = await call_tool(registry, "get_order_status", {"order_id": "order-1"}, token="caller-token")

    assert result == {"id": "order-1", "status": "paid"}
    clients.orders.get_order_status.assert_awaited_once_with(order_id="order-1", token="caller-token")


async def test_call_tool_forwards_token_for_cart_write_tools():
    clients = _fake_clients()
    clients.orders.add_to_cart = AsyncMock(return_value={"items": []})
    registry = build_tool_registry(clients)

    await call_tool(registry, "add_to_cart", {"product_id": "prod-1", "quantity": 2}, token="customer-token")

    clients.orders.add_to_cart.assert_awaited_once_with(product_id="prod-1", quantity=2, token="customer-token")


async def test_call_tool_unknown_name_raises():
    registry = build_tool_registry(_fake_clients())
    with pytest.raises(ToolNotFoundError):
        await call_tool(registry, "not_a_real_tool", {}, token="caller-token")


def test_checkout_and_payment_tools_are_never_registered():
    # STR-146: the enforced boundary — no prompt-level instruction, no
    # runtime check, just the absence of an entry to route to. Any name
    # even loosely resembling "finalize a purchase" must not appear.
    registry = build_tool_registry(_fake_clients())
    forbidden_substrings = ("checkout", "charge", "payment", "pay", "finalize", "place_order")
    for name in registry:
        lowered = name.lower()
        assert not any(term in lowered for term in forbidden_substrings), name
