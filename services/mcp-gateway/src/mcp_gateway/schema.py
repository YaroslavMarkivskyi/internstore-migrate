from typing import Any, TypedDict


class ToolSpec(TypedDict):
    name: str
    description: str
    input_schema: dict[str, Any]


# Static JSON Schema catalog for every tool in the registry — the `Tool`
# list the MCP server advertises on `tools/list` (see mcp_server.py). Kept
# separate from the callables themselves (router.py) since a tool's public
# contract (name / description / args) is Gateway API surface, independent of
# which domain client implements it. Still hand-maintained rather than
# derived from the method signatures — a noted follow-up (see README).
TOOL_SPECS: list[ToolSpec] = [
    {
        "name": "get_order_status",
        "description": "Get an order's status, items, timestamps, and contact info.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "Order UUID"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "list_customer_orders",
        "description": "List a customer's most recent orders with status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer owner_id (Firebase sub or guest_id)"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_my_orders",
        "description": (
            "List the current customer's own recent orders (id, status, items, timestamps). "
            "Scoped to the caller — takes no customer id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 5}},
            "required": [],
        },
    },
    {
        "name": "get_my_order",
        "description": (
            "Get one of the current customer's own orders by id (status, items, timestamps). "
            "Only the caller's own orders are visible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "Order UUID from a get_my_orders result"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "get_pending_orders",
        "description": "Get orders stuck in Pending status for admin review.",
        "input_schema": {
            "type": "object",
            "properties": {"older_than_minutes": {"type": "integer", "default": 60}},
            "required": [],
        },
    },
    {
        "name": "get_cart",
        "description": (
            "Get the caller's own current cart. Scoped to whoever's token was forwarded — there is "
            "no customer_id argument. Returns {items: [{product_id, name, quantity, unit_price, "
            "line_total}], total}."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_to_cart",
        "description": (
            "Add a quantity of a product to the caller's own cart (accumulates if already present). "
            "Returns the full updated cart in the same shape as get_cart, including the new total."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product UUID"},
                "quantity": {"type": "integer", "description": "Quantity to add, must be positive"},
            },
            "required": ["product_id", "quantity"],
        },
    },
    {
        "name": "remove_from_cart",
        "description": (
            "Remove a product entirely from the caller's own cart. Returns the full updated cart in "
            "the same shape as get_cart, including the new total."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"product_id": {"type": "string", "description": "Product UUID"}},
            "required": ["product_id"],
        },
    },
    {
        "name": "check_availability",
        "description": "Check available stock for a product across warehouses.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product UUID"},
                "quantity": {"type": "integer", "description": "Requested quantity"},
            },
            "required": ["product_id", "quantity"],
        },
    },
    {
        "name": "get_stock_levels",
        "description": "List all products and quantities in a warehouse.",
        "input_schema": {
            "type": "object",
            "properties": {"warehouse_id": {"type": "string", "description": "Stock/warehouse UUID"}},
            "required": ["warehouse_id"],
        },
    },
    {
        "name": "get_unavailable_items",
        "description": "List items marked unavailable due to temperature violations.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_products",
        "description": "Semantic search over the product catalog, with optional price/category filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
                "filters": {
                    "type": "object",
                    "description": "Optional. All fields optional.",
                    "properties": {
                        "price_min": {"type": "number"},
                        "price_max": {"type": "number"},
                        "category": {"type": "string"},
                    },
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_similar_products",
        "description": (
            "Find products similar to a given one (by name/description/category), for suggesting "
            "alternatives when something is unavailable or the customer wants options. Takes the "
            "product_id from a prior search_products / get_cart result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product UUID to find alternatives to"},
                "limit": {"type": "integer", "default": 3},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "search_help",
        "description": (
            "Search the customer-facing FAQ / policy corpus (delivery, shipping, returns, refunds, "
            "payment, product safety / the cold chain, accounts). Use for any question about how the "
            "store works rather than about a specific product. Returns the most relevant help "
            "sections as {source, heading, content}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The customer's question, in their own words"},
                "limit": {"type": "integer", "default": 3},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_product",
        "description": "Get full product details including temperature range.",
        "input_schema": {
            "type": "object",
            "properties": {"product_id": {"type": "string", "description": "Product UUID"}},
            "required": ["product_id"],
        },
    },
    {
        "name": "list_categories",
        "description": "List all product categories.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_store_temperature",
        "description": "Get a store's current temperature and violation status.",
        "input_schema": {
            "type": "object",
            "properties": {"store_id": {"type": "string", "description": "Store UUID"}},
            "required": ["store_id"],
        },
    },
    {
        "name": "get_temperature_readings",
        "description": "Get historical temperature readings for a store.",
        "input_schema": {
            "type": "object",
            "properties": {
                "store_id": {"type": "string", "description": "Store UUID"},
                "period": {"type": "string", "enum": ["week", "month", "3months", "all"], "default": "week"},
            },
            "required": ["store_id"],
        },
    },
    {
        "name": "get_active_incidents",
        "description": "List all open temperature incidents across every store.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_visit_log",
        "description": "Get a warehouse's access log with video URLs, admin use only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "warehouse_id": {"type": "string", "description": "Warehouse UUID"},
                "date_from": {"type": "string", "description": "ISO 8601 datetime"},
                "date_to": {"type": "string", "description": "ISO 8601 datetime"},
            },
            "required": ["warehouse_id", "date_from", "date_to"],
        },
    },
    {
        "name": "get_active_users",
        "description": "List registered employees and suppliers with warehouse access, admin use only.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_room_summary",
        "description": "Get the last messages from a chat room, admin use only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["room_id"],
        },
    },
    {
        "name": "list_active_rooms",
        "description": "List chat rooms with unread messages, admin use only.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

TOOL_SPECS_BY_NAME: dict[str, ToolSpec] = {spec["name"]: spec for spec in TOOL_SPECS}
