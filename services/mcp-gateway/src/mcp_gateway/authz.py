"""Server-side tool-tier authorization.

Which tools a caller may list / call, keyed off their internal-token role.
Until now this gating lived only on the agent side
(`ai_assistant/adk/prompts.py`'s `McpToolset(tool_filter=...)`); the Gateway
handed every tool to everyone and relied on the downstream `/admin` services
to 403 a customer token. This makes the Gateway itself the boundary: a
customer token that reaches `/mcp` directly never even sees `get_visit_log`.

The tiers mirror the agent-side allow-lists exactly. Kept here as their own
copy — this repo has no shared-library mechanism between services (same
reason `observability.py` etc. are duplicated).
"""

# Cart-scoped or read-only and customer/guest-safe with a forwarded customer
# token. Matches ai_assistant/adk/prompts.SHOPPING_TOOL_NAMES.
_SHOPPING_TIER = frozenset(
    {
        "search_products",
        "get_similar_products",
        "get_product",
        "list_categories",
        "check_availability",
        "get_my_orders",
        "get_my_order",
        "get_cart",
        "add_to_cart",
        "remove_from_cart",
        "search_help",
    }
)

# Read-only operations tools. Matches ai_assistant/adk/prompts.ADMIN_TOOL_NAMES.
_ADMIN_TIER = frozenset(
    {
        "search_products",
        "get_product",
        "list_categories",
        "get_order_status",
        "list_customer_orders",
        "get_pending_orders",
        "check_availability",
        "get_stock_levels",
        "get_unavailable_items",
        "get_store_temperature",
        "get_temperature_readings",
        "get_active_incidents",
        "get_room_summary",
        "list_active_rooms",
        "get_active_users",
        "get_visit_log",
    }
)


def authorized_tools(role: str, all_tool_names: frozenset[str]) -> frozenset[str]:
    """The subset of `all_tool_names` this role may list and call.

    `assistant` is this project's own service identity (not a forwarded
    end-user token) and gets everything; an unknown role gets nothing.
    """
    if role == "assistant":
        return all_tool_names
    if role == "admin":
        return _ADMIN_TIER & all_tool_names
    if role in ("customer", "guest"):
        return _SHOPPING_TIER & all_tool_names
    return frozenset()
