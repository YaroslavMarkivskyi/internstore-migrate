import json
import logging

from openai import AsyncOpenAI

from ai_assistant.auth_backend_client import AuthBackendClient
from ai_assistant.mcp_client import MCPGatewayClient
from ai_assistant.token_manager import RefreshableToken

logger = logging.getLogger(__name__)

# STR-146: the exact tool set the ticket allows this agent — no more. The
# Gateway's registry has no checkout/charge_payment/etc entry to begin with
# (see mcp_gateway/router.py), so that boundary holds regardless of this
# list; this filter additionally keeps the *other* admin-only tools
# (get_visit_log, get_pending_orders, ...) out of what the model is even
# offered, since a shopping conversation has no legitimate reason to see
# them.
SHOPPING_TOOL_NAMES = ("search_products", "get_cart", "add_to_cart", "remove_from_cart")

SYSTEM_PROMPT = """\
You are InternStore's shopping assistant. You can search products and manage \
the customer's cart. You CANNOT check out, process payments, or take any \
action beyond building a cart. If asked to complete a purchase, tell the \
customer to review their cart and check out themselves.
Before adding items, check the current cart with get_cart so you don't \
create duplicate lines or ignore quantities already there.
When you add or remove a cart item, say so plainly in your reply (what \
changed, how many items are in the cart now, and the price if you have it) \
so the customer doesn't have to check the cart UI separately.
Always be concise and professional."""

DEFAULT_MAX_ITERATIONS = 5
DEFAULT_REFRESH_MARGIN_SECONDS = 15

FALLBACK_REPLY = "I wasn't able to finish that — please check your cart directly, or try rephrasing your request."


def _to_openai_tools(tool_specs: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": spec["input_schema"],
            },
        }
        for spec in tool_specs
        if spec["name"] in SHOPPING_TOOL_NAMES
    ]


async def run_shopping_agent(
    *,
    openai_client: AsyncOpenAI,
    mcp_client: MCPGatewayClient,
    auth_backend_client: AuthBackendClient,
    chat_model: str,
    message: str,
    token: RefreshableToken,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    refresh_margin_seconds: int = DEFAULT_REFRESH_MARGIN_SECONDS,
) -> str:
    """Runs the shopping ReAct loop for a single customer message: search
    products and read/mutate the cart via the MCP Gateway, forwarding (and
    refreshing — see token_manager.py) the customer's own internal-token the
    whole way, until the model produces a final answer with no further tool
    calls, or `max_iterations` is reached (reuses STR-137's cap of 5)."""
    tool_specs = await mcp_client.list_tools(token.value)
    openai_tools = _to_openai_tools(tool_specs)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]

    for _ in range(max_iterations):
        await token.ensure_fresh(auth_backend_client, refresh_margin_seconds)

        response = await openai_client.chat.completions.create(
            model=chat_model,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
        )
        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls or []

        if not tool_calls:
            return assistant_message.content or ""

        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.function.name, "arguments": call.function.arguments},
                    }
                    for call in tool_calls
                ],
            }
        )

        for call in tool_calls:
            try:
                arguments = json.loads(call.function.arguments or "{}")
                result = await mcp_client.call_tool(token.value, call.function.name, arguments)
                content = json.dumps(result)
            except Exception as exc:
                # Surfaced back to the model as a tool error (e.g. "product
                # not found", a 401 from a stale token the refresh above
                # missed) so it can recover or apologize, rather than
                # crashing the whole request over one bad tool call.
                logger.warning("Shopping agent tool call %s failed: %s", call.function.name, exc)
                content = json.dumps({"error": str(exc)})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    return FALLBACK_REPLY
