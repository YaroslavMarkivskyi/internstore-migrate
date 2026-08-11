from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from ai_assistant.chat_client import ChatClient
from ai_assistant.embeddings import search_similar_products
from ai_assistant.orders_client import OrdersClient

SYSTEM_PROMPT = """\
You are a helpful customer support assistant for InternStore, a warehouse management platform.
You can see the customer's order history and relevant product information.
You help with: order status, product information, temperature requirements, availability.
You CANNOT: modify orders, process refunds, change inventory.
If you cannot help, suggest the customer switch to human support.
Always be concise and professional."""


def _sender_role_to_map(sender_type: str) -> str:
    # Chat's sender_type values map onto OpenAI's roles: the assistant's own
    # past replies are "assistant", everyone else (customer, admin) reads as
    # "user" from the model's point of view.
    return "assistant" if sender_type == "assistant" else "user"


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


async def build_messages(
    *,
    session: AsyncSession,
    openai_client: AsyncOpenAI,
    embedding_model: str,
    chat_client: ChatClient,
    orders_client: OrdersClient,
    room_id: str,
    sender_id: str,
    sender_role: str,
    customer_message: str,
    conversation_history_limit: int,
    order_history_limit: int,
    product_context_limit: int,
) -> list[dict]:
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
        session, openai_client, embedding_model, customer_message, product_context_limit
    )
    context_sections.append(_format_product_context(products))

    system_content = SYSTEM_PROMPT + "\n\n" + "\n\n".join(context_sections)

    return [
        {"role": "system", "content": system_content},
        *conversation,
        {"role": "user", "content": customer_message},
    ]
