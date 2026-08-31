import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from google import genai
from google.genai import types

from ai_assistant.auth_backend_client import AuthBackendClient
from ai_assistant.mcp_client import MCPGatewayClient
from ai_assistant.token_manager import RefreshableToken

logger = logging.getLogger(__name__)


@dataclass
class Delta:
    """A piece of the assistant's final answer, streamed as the model
    produces it (see run_shopping_agent_stream)."""

    text: str


@dataclass
class Reset:
    """The model streamed some answer text and then decided to call a tool
    after all — whatever Deltas were emitted this turn are not part of the
    final answer and must be discarded by the consumer."""


StreamEvent = Delta | Reset

# STR-146: the exact tool set this agent is allowed — no more. The Gateway's
# registry has no checkout/charge_payment/etc entry to begin with (see
# mcp_gateway/router.py), so that boundary holds regardless of this list;
# this filter additionally keeps the *admin-only* tools (get_visit_log,
# get_pending_orders, get_stock_levels, get_order_status/list_customer_orders
# — those hit /admin, need an admin-or-assistant token) out of what the
# model is even offered. Everything here is either cart-scoped or
# read-only and customer/guest-safe with the forwarded customer token:
#   search_products / get_product / list_categories  — catalog reads
#   check_availability                               — inventory "any"-tier read
#   get_my_orders / get_my_order                     — the caller's OWN orders,
#                                                      scoped to their token's sub
#   get_cart / add_to_cart / remove_from_cart        — the caller's own cart
#   search_help                                      — FAQ / policy corpus
#                                                      (delivery, returns,
#                                                      payment, cold chain),
#                                                      read-only, no token
SHOPPING_TOOL_NAMES = (
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
)

SYSTEM_PROMPT = """\
You are InternStore's shopping assistant. You can search the catalogue, check \
stock, look up the customer's own past orders, and manage the customer's \
cart. You CANNOT check out, process payments, cancel or change an order, or \
take any action beyond building a cart. If asked to complete a purchase, \
tell the customer to review their cart and check out themselves; for changes \
to an existing order, tell them to contact support.
Before adding items, check the current cart with get_cart so you don't \
create duplicate lines or ignore quantities already there.
If a product the customer wants isn't available, or they ask for something \
"like" a product or for alternatives, call get_similar_products with that \
product's id and offer the closest matches.
CRITICAL: the "product_id" field of a search_products or get_cart result \
is an opaque UUID (e.g. "3f9a...-...-...-...-..."), 36 characters with \
four dashes. Use it verbatim wherever a product_id is needed — as the \
add_to_cart / remove_from_cart argument, AND inside the product link \
described below. Never invent one, never pass a product's name, \
description, price, or any digits pulled out of the name as a product_id, \
even if they look like an identifier. If you don't have a real product_id \
from a tool result yet, call search_products or get_cart first.
For questions about delivery, shipping, returns, refunds, payment, product \
safety / the cold chain, accounts, or anything about store policy, call \
search_help and answer only from what it returns — don't guess a policy. If \
search_help returns nothing relevant, say you're not sure and point the \
customer to support.
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


def _build_contents(
    *, message: str, viewing_product_id: str | None, history: list[dict] | None
) -> list[types.Content]:
    contents: list[types.Content] = [
        types.Content(role=_sender_role_to_map(entry["sender_type"]), parts=[types.Part(text=entry["content"])])
        for entry in (history or [])
        if entry.get("content")
    ]
    # STR-XXX: if the customer had a product page open, tell the model
    # which product "this"/"it" refers to — as a separate turn so it reads
    # as context, not as something the customer typed. viewing_product_id
    # is a Chat-validated UUID (see chat/ws/room.py); still, the model must
    # confirm it via get_product before quoting details, since a stale tab
    # could point at a deleted product.
    if viewing_product_id:
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=(
                            f"(Context: the customer is viewing the product page for product_id "
                            f"{viewing_product_id}. If they say 'this', 'it', or 'this product' "
                            f"without naming one, they mean that product. Call get_product to "
                            f"confirm its current details before quoting them.)"
                        )
                    )
                ],
            )
        )
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    return contents


async def _run_tool_calls(
    mcp_client: MCPGatewayClient, token: RefreshableToken, function_calls: list
) -> types.Content:
    response_parts = []
    for call in function_calls:
        try:
            result = await mcp_client.call_tool(token.value, call.name, dict(call.args or {}))
            function_response = {"result": result}
        except Exception as exc:
            # Surfaced back to the model as a tool error (e.g. "product
            # not found", a 401 from a stale token the refresh above
            # missed, or a 404 for a hallucinated tool name the Gateway's
            # registry has no entry for — see mcp_gateway/router.py) so it
            # can recover or apologize, rather than crashing the whole
            # request over one bad call.
            logger.warning("Shopping agent tool call %s(%s) failed: %s", call.name, call.args, exc)
            function_response = {"error": str(exc)}
        response_parts.append(types.Part.from_function_response(name=call.name, response=function_response))
    return types.Content(role="tool", parts=response_parts)


async def run_shopping_agent_stream(
    *,
    genai_client: genai.Client,
    mcp_client: MCPGatewayClient,
    auth_backend_client: AuthBackendClient,
    chat_model: str,
    message: str,
    viewing_product_id: str | None = None,
    token: RefreshableToken,
    history: list[dict] | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    refresh_margin_seconds: int = DEFAULT_REFRESH_MARGIN_SECONDS,
) -> AsyncIterator[StreamEvent]:
    """Streaming form of the shopping ReAct loop: yields `Delta`s of the
    final answer as the model produces them, so the customer sees the reply
    build up token-by-token rather than after a multi-second silence.

    Only the answer turn is streamed — turns that end in tool calls emit
    nothing (or a `Reset`, in the uncommon case the model streamed a text
    preamble before deciding to call a tool). `run_shopping_agent` wraps
    this to recover the plain-string reply for non-streaming callers and
    tests.

    `history` / `viewing_product_id` behave exactly as in the pre-streaming
    loop — see STR-148 (history antecedents for "add it to my cart") and
    the product-page context turn below."""
    tool_specs = await mcp_client.list_tools(token.value)
    tools = _to_genai_tools(tool_specs)
    contents = _build_contents(message=message, viewing_product_id=viewing_product_id, history=history)
    config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=tools)

    for _ in range(max_iterations):
        await token.ensure_fresh(auth_backend_client, refresh_margin_seconds)

        stream = await genai_client.aio.models.generate_content_stream(
            model=chat_model, contents=contents, config=config
        )

        text_parts: list[str] = []
        function_calls: list = []
        streamed_text = False
        async for chunk in stream:
            for call in chunk.function_calls or []:
                function_calls.append(call)
            delta = chunk.text or ""
            if not delta:
                continue
            text_parts.append(delta)
            # Stream text out live, but only while this still looks like a
            # pure answer turn. If a function_call has already shown up in
            # this turn, the text is a preamble to a tool call, not the
            # answer — keep it for the model's own transcript, don't show it.
            if not function_calls:
                streamed_text = True
                yield Delta(text=delta)

        if not function_calls:
            if not streamed_text and text_parts:
                yield Delta(text="".join(text_parts))
            return

        if streamed_text:
            # Streamed some answer text, then the model called a tool after
            # all — tell the consumer to drop what it showed.
            yield Reset()

        # The model's own turn goes back into `contents` so the next
        # request has continuity — reassembled here (streaming gives no
        # aggregate Content object, unlike generate_content).
        model_parts: list[types.Part] = []
        if text_parts:
            model_parts.append(types.Part(text="".join(text_parts)))
        model_parts.extend(types.Part(function_call=call) for call in function_calls)
        contents.append(types.Content(role="model", parts=model_parts))

        contents.append(await _run_tool_calls(mcp_client, token, function_calls))

    yield Delta(text=FALLBACK_REPLY)


async def run_shopping_agent(
    *,
    genai_client: genai.Client,
    mcp_client: MCPGatewayClient,
    auth_backend_client: AuthBackendClient,
    chat_model: str,
    message: str,
    viewing_product_id: str | None = None,
    token: RefreshableToken,
    history: list[dict] | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    refresh_margin_seconds: int = DEFAULT_REFRESH_MARGIN_SECONDS,
) -> str:
    """Non-streaming wrapper over `run_shopping_agent_stream` — collects the
    streamed answer into the final plain string, honouring any `Reset`."""
    buffer: list[str] = []
    async for event in run_shopping_agent_stream(
        genai_client=genai_client,
        mcp_client=mcp_client,
        auth_backend_client=auth_backend_client,
        chat_model=chat_model,
        message=message,
        viewing_product_id=viewing_product_id,
        token=token,
        history=history,
        max_iterations=max_iterations,
        refresh_margin_seconds=refresh_margin_seconds,
    ):
        if isinstance(event, Reset):
            buffer.clear()
        else:
            buffer.append(event.text)
    return "".join(buffer)
