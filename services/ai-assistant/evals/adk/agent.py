"""The shopping agent, wired for evaluation: real prompt + real model, but
its tools are backed by the in-memory `FakeMCPGatewayClient` (fixed
catalogue, a mutable cart, recorded calls) so only the model is live.

`AgentEvaluator` (see test_adk_evals.py) loads `root_agent` from this module
by convention.
"""

import os

from ai_assistant.adk.prompts import SHOPPING_INSTRUCTION
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext

from evals.harness import FakeMCPGatewayClient

_fake = FakeMCPGatewayClient()


def _reset(_ctx: CallbackContext) -> None:
    # Each eval invocation starts from an empty cart / clean call log.
    _fake.calls.clear()
    _fake.cart.clear()
    _fake.orders_empty = False


async def search_products(query: str, price_max: float | None = None, price_min: float | None = None) -> list:
    """Semantic search over the product catalogue, with optional price filters."""
    filters: dict = {}
    if price_max is not None:
        filters["price_max"] = price_max
    if price_min is not None:
        filters["price_min"] = price_min
    return await _fake.call_tool("t", "search_products", {"query": query, "filters": filters})


async def get_product(product_id: str) -> dict:
    """Full details for one product, by the UUID from a prior result."""
    return await _fake.call_tool("t", "get_product", {"product_id": product_id})


async def get_cart() -> dict:
    """The customer's current cart: items (name, quantity, line_total) and the total."""
    return await _fake.call_tool("t", "get_cart", {})


async def add_to_cart(product_id: str, quantity: int) -> dict:
    """Add a quantity of a product (by UUID) to the cart; returns the full updated cart."""
    return await _fake.call_tool("t", "add_to_cart", {"product_id": product_id, "quantity": quantity})


async def get_my_orders(limit: int = 5) -> list:
    """The customer's own recent orders (id, status, items)."""
    return await _fake.call_tool("t", "get_my_orders", {"limit": limit})


async def check_availability(product_id: str, quantity: int) -> dict:
    """Whether a quantity of a product is currently in stock."""
    return await _fake.call_tool("t", "check_availability", {"product_id": product_id, "quantity": quantity})


async def search_help(query: str, limit: int = 3) -> list:
    """Search the FAQ / policy corpus (delivery, returns, refunds, payment)."""
    return await _fake.call_tool("t", "search_help", {"query": query, "limit": limit})


root_agent = LlmAgent(
    name="shopping_assistant",
    model=os.environ.get("CHAT_MODEL", "gemini-2.5-flash"),
    instruction=SHOPPING_INSTRUCTION,
    tools=[
        search_products,
        get_product,
        get_cart,
        add_to_cart,
        get_my_orders,
        check_availability,
        search_help,
    ],
    before_agent_callback=_reset,
)
