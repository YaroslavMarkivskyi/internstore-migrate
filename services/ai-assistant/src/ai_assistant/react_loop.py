import logging

from google import genai
from google.genai import types

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
CRITICAL: the "product_id" field of a search_products or get_cart result \
is an opaque UUID (e.g. "3f9a...-...-...-...-..."), 36 characters with \
four dashes. Use it verbatim wherever a product_id is needed — as the \
add_to_cart / remove_from_cart argument, AND inside the product link \
described below. Never invent one, never pass a product's name, \
description, price, or any digits pulled out of the name as a product_id, \
even if they look like an identifier. If you don't have a real product_id \
from a tool result yet, call search_products or get_cart first.
When you add or remove a cart item, say so plainly in your reply (what \
changed, how many items are in the cart now, and the price if you have it) \
so the customer doesn't have to check the cart UI separately.
Whenever you mention a specific product from a tool result, write its name \
as a Markdown link to its page: [<name>](/products/<product_id>) — the \
36-character UUID from that same result, nothing else. Link each product \
the first time you name it in a reply; plain text for later mentions.
Reply in plain sentences only — the product links above are the ONLY \
Markdown to use. No bullet lists, headings, bold, or other formatting.
Always be concise and professional."""

DEFAULT_MAX_ITERATIONS = 5
DEFAULT_REFRESH_MARGIN_SECONDS = 15

FALLBACK_REPLY = "I wasn't able to finish that — please check your cart directly, or try rephrasing your request."


def _to_genai_tools(tool_specs: list[dict]) -> list[types.Tool]:
    # STR-161b: a single Tool bundling every allowed FunctionDeclaration —
    # Gemini's request shape, vs. OpenAI's one {"type": "function", ...}
    # entry per tool. parameters_json_schema takes the Gateway's own raw
    # JSON Schema (schema.py's TOOL_SPECS) as-is, no translation needed.
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=spec["name"], description=spec["description"], parameters_json_schema=spec["input_schema"]
                )
                for spec in tool_specs
                if spec["name"] in SHOPPING_TOOL_NAMES
            ]
        )
    ]


def _sender_role_to_map(sender_type: str) -> str:
    # STR-161b: Gemini's content roles are "user"/"model", not OpenAI's
    # "user"/"assistant" — same mapping as context.py's copy for the
    # guest/Kafka-driven agent.
    return "model" if sender_type == "assistant" else "user"


async def run_shopping_agent(
    *,
    genai_client: genai.Client,
    mcp_client: MCPGatewayClient,
    auth_backend_client: AuthBackendClient,
    chat_model: str,
    message: str,
    token: RefreshableToken,
    history: list[dict] | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    refresh_margin_seconds: int = DEFAULT_REFRESH_MARGIN_SECONDS,
) -> str:
    """Runs the shopping ReAct loop for a single customer message: search
    products and read/mutate the cart via the MCP Gateway, forwarding (and
    refreshing — see token_manager.py) the customer's own internal-token the
    whole way, until the model produces a final answer with no further tool
    calls, or `max_iterations` is reached (reuses STR-137's cap of 5).

    `history` (Chat's own room messages, oldest-first — see
    ChatClient.get_recent_messages) gives the model the prior turns of this
    conversation. Found missing during STR-148's live verification: without
    it, each WebSocket message hit this loop as a completely isolated
    exchange, so "add it to my cart" right after "find me a Gouda under
    $20" had no idea what "it" referred to — every unit test happened to
    mock a single self-contained turn, so this never surfaced until a real
    multi-turn conversation against a real model."""
    tool_specs = await mcp_client.list_tools(token.value)
    tools = _to_genai_tools(tool_specs)

    contents: list[types.Content] = [
        types.Content(role=_sender_role_to_map(entry["sender_type"]), parts=[types.Part(text=entry["content"])])
        for entry in (history or [])
        if entry.get("content")
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

    config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=tools)

    for _ in range(max_iterations):
        await token.ensure_fresh(auth_backend_client, refresh_margin_seconds)

        response = await genai_client.aio.models.generate_content(model=chat_model, contents=contents, config=config)
        function_calls = response.function_calls or []

        if not function_calls:
            return response.text or ""

        # STR-161b: the model's own turn (both any text and the
        # function_call parts) has to go back into `contents` verbatim —
        # Gemini expects the exact Content it produced, not a
        # re-serialized summary, so the follow-up call has continuity
        # (mirrors OpenAI's `assistant_message` append, just a whole
        # Content object instead of a hand-built dict).
        contents.append(response.candidates[0].content)

        response_parts = []
        for call in function_calls:
            try:
                result = await mcp_client.call_tool(token.value, call.name, dict(call.args or {}))
                function_response = {"result": result}
            except Exception as exc:
                # Surfaced back to the model as a tool error (e.g. "product
                # not found", a 401 from a stale token the refresh above
                # missed, or a 404 for a hallucinated tool name the
                # Gateway's registry has no entry for — see
                # mcp_gateway/router.py) so it can recover or apologize,
                # rather than crashing the whole request over one bad call.
                logger.warning("Shopping agent tool call %s(%s) failed: %s", call.name, call.args, exc)
                function_response = {"error": str(exc)}
            response_parts.append(types.Part.from_function_response(name=call.name, response=function_response))

        contents.append(types.Content(role="tool", parts=response_parts))

    return FALLBACK_REPLY
