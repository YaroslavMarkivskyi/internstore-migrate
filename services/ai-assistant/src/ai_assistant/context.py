from google import genai
from sqlalchemy.ext.asyncio import AsyncSession

from ai_assistant.chat_client import ChatClient
from ai_assistant.embeddings import search_similar_products
from ai_assistant.help import search_help
from ai_assistant.orders_client import OrdersClient

SYSTEM_PROMPT = """\
You are a helpful customer support assistant for InternStore, a warehouse management platform.
You can see the customer's order history, relevant product information, and
relevant help / policy articles (delivery, returns, refunds, payment, the
cold chain, accounts).
You help with: order status, product information, temperature requirements,
availability, and store-policy questions.
Answer any policy question strictly from the help articles below — do not
guess a policy. If none of them cover the question, say you're not sure and
suggest human support.
You CANNOT: modify orders, process refunds, change inventory, or add things
to a cart.
If you cannot help, suggest the customer switch to human support.
Write the whole reply in ONE language — either English or Ukrainian,
matching the customer's latest message; never mix the two in one reply. If
their language is unclear, use English.
Always be concise and professional."""


def _sender_role_to_map(sender_type: str) -> str:
    # STR-161b: Gemini's two content roles are "user" and "model" (no
    # "assistant", no "system" — the system prompt is a separate
    # system_instruction, see build_messages below) — the assistant's own
    # past replies map to "model", everyone else (customer, admin) to
    # "user".
    return "model" if sender_type == "assistant" else "user"


def _format_order_history(orders: list[dict]) -> str:
    if not orders:
        return "Customer's recent orders: none."
    lines = ["Customer's recent orders:"]
    for order in orders:
        items = ", ".join(f"{item['quantity']}x {item['product_id']}" for item in order["items"])
        lines.append(f"- Order {order['id']} [{order['status']}] placed {order['created_at']}: {items}")
    return "\n".join(lines)


def _format_product_context(products: list[dict]) -> str:
    if not products:
        return "Relevant products: none found."
    lines = ["Relevant products:"]
    for product in products:
        lines.append(f"- {product['name']}: {product.get('description') or 'no description'}")
    return "\n".join(lines)


def _format_help_context(chunks: list[dict]) -> str:
    if not chunks:
        return "Relevant help / policy articles: none found."
    lines = ["Relevant help / policy articles (answer policy questions only from these):"]
    for chunk in chunks:
        lines.append(f"- {chunk['heading']}: {chunk['content']}")
    return "\n".join(lines)


async def build_messages(
    *,
    session: AsyncSession,
    genai_client: genai.Client,
    embedding_model: str,
    embedding_dimensions: int,
    chat_client: ChatClient,
    orders_client: OrdersClient,
    room_id: str,
    sender_id: str,
    sender_role: str,
    customer_message: str,
    conversation_history_limit: int,
    order_history_limit: int,
    product_context_limit: int,
    help_context_limit: int = 2,
) -> tuple[str, list[dict]]:
    """Returns (system_instruction, contents) rather than a single OpenAI-
    style messages list — Gemini takes the system prompt as its own
    GenerateContentConfig.system_instruction, not a "system"-role content
    entry (see agent.generate_reply)."""
    history = await chat_client.get_recent_messages(room_id, conversation_history_limit)
    conversation = [
        {"role": _sender_role_to_map(message["sender_type"]), "content": message["content"]}
        for message in history
        if message["content"]
    ]

    context_sections = []
    # STR-148: was `is_registered_customer(sender_id)`, a heuristic that
    # guessed "customer" whenever sender_id merely looked like a UUID —
    # broken by construction, since guest session ids are uuid4() too (see
    # auth-backend's GuestSessionStore). sender_role now comes straight
    # from the CustomerMessageSent event payload (chat/ws/room.py), not a
    # guess. In practice this function is currently only ever called for
    # guests (chat_events.py skips registered customers before reaching
    # here — see that module), but takes the real role rather than baking
    # that assumption in here too.
    if sender_role == "customer":
        orders = await orders_client.get_recent_orders(sender_id, order_history_limit)
        context_sections.append(_format_order_history(orders))

    products = await search_similar_products(
        session, genai_client, embedding_model, customer_message, embedding_dimensions, product_context_limit
    )
    context_sections.append(_format_product_context(products))

    # STR-XXX: guests get no MCP tools (they're not the shopping agent), so
    # give the non-agentic loop the same FAQ / policy corpus the shopping
    # agent reaches via search_help — retrieved and stuffed into the prompt
    # here, the same way product context is.
    help_chunks = await search_help(
        session, genai_client, embedding_model, embedding_dimensions, customer_message, help_context_limit
    )
    context_sections.append(_format_help_context(help_chunks))

    system_instruction = SYSTEM_PROMPT + "\n\n" + "\n\n".join(context_sections)

    return system_instruction, [
        *conversation,
        {"role": "user", "content": customer_message},
    ]
