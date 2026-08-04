from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp_gateway.tools.catalog import CatalogToolsClient, ProductSearchClient
from mcp_gateway.tools.chat import ChatToolsClient
from mcp_gateway.tools.inventory import InventoryToolsClient
from mcp_gateway.tools.orders import OrdersToolsClient
from mcp_gateway.tools.security import SecurityToolsClient
from mcp_gateway.tools.telemetry import TelemetryToolsClient

ToolFunc = Callable[..., Awaitable[Any]]


class ToolNotFoundError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Unknown tool: {name}")


@dataclass
class GatewayClients:
    orders: OrdersToolsClient
    inventory: InventoryToolsClient
    catalog: CatalogToolsClient
    product_search: ProductSearchClient
    telemetry: TelemetryToolsClient
    security: SecurityToolsClient
    chat: ChatToolsClient


# Built per-app from a GatewayClients instance (see main.py's create_app)
# rather than as a static module-level dict, since each entry is a bound
# client method that needs real Settings (base URLs, secrets) wired in
# first -- a plain name->function dict evaluated at import time would have
# nothing to bind to.
def build_tool_registry(clients: GatewayClients) -> dict[str, ToolFunc]:
    return {
        "get_order_status": clients.orders.get_order_status,
        "list_customer_orders": clients.orders.list_customer_orders,
        "get_pending_orders": clients.orders.get_pending_orders,
        "check_availability": clients.inventory.check_availability,
        "get_stock_levels": clients.inventory.get_stock_levels,
        "get_unavailable_items": clients.inventory.get_unavailable_items,
        "search_products": clients.product_search.search_products,
        "get_product": clients.catalog.get_product,
        "list_categories": clients.catalog.list_categories,
        "get_store_temperature": clients.telemetry.get_store_temperature,
        "get_temperature_readings": clients.telemetry.get_temperature_readings,
        "get_active_incidents": clients.telemetry.get_active_incidents,
        "get_visit_log": clients.security.get_visit_log,
        "get_active_users": clients.security.get_active_users,
        "get_room_summary": clients.chat.get_room_summary,
        "list_active_rooms": clients.chat.list_active_rooms,
    }


async def call_tool(registry: dict[str, ToolFunc], name: str, arguments: dict[str, Any]) -> Any:
    if name not in registry:
        raise ToolNotFoundError(name)
    return await registry[name](**arguments)
