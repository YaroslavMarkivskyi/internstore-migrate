from types import SimpleNamespace
from unittest.mock import AsyncMock

from ai_assistant.context import SYSTEM_PROMPT, build_messages

REGISTERED_CUSTOMER_ID = "11111111-1111-1111-1111-111111111111"
# STR-148: deliberately also a plain UUID — guest session ids are uuid4()
# too (see auth-backend's GuestSessionStore), the exact shape collision
# that made the old sender_id-shape guess (is_registered_customer) wrong.
GUEST_ID = "22222222-2222-2222-2222-222222222222"
ROOM_ID = f"room_{REGISTERED_CUSTOMER_ID}"


def _fake_genai_client() -> AsyncMock:
    client = AsyncMock()
    client.aio.models.embed_content = AsyncMock(
        return_value=SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1] * 1536)])
    )
    return client


def _chat_client(history: list[dict]) -> AsyncMock:
    client = AsyncMock()
    client.get_recent_messages = AsyncMock(return_value=history)
    return client


def _orders_client(orders: list[dict]) -> AsyncMock:
    client = AsyncMock()
    client.get_recent_orders = AsyncMock(return_value=orders)
    return client


async def _fake_session_returning(rows: list) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=iter(rows))
    return session


async def test_build_messages_assembles_history_orders_and_products():
    history = [
        {"sender_type": "assistant", "content": "How can I help?"},
        {"sender_type": "customer", "content": "Where's my order?"},
    ]
    orders = [
        {
            "id": "order-1",
            "status": "PAID",
            "created_at": "2026-08-01T00:00:00Z",
            "items": [{"product_id": "prod-1", "quantity": 2}],
        }
    ]
    product_rows = [SimpleNamespace(product_id="prod-1", name="Frozen Peas", description="1kg bag")]

    session = await _fake_session_returning(product_rows)
    genai_client = _fake_genai_client()
    chat_client = _chat_client(history)
    orders_client = _orders_client(orders)

    system_instruction, contents = await build_messages(
        session=session,
        genai_client=genai_client,
        embedding_model="gemini-embedding-001",
        embedding_dimensions=1536,
        chat_client=chat_client,
        orders_client=orders_client,
        room_id=ROOM_ID,
        sender_id=REGISTERED_CUSTOMER_ID,
        sender_role="customer",
        customer_message="Where's my order?",
        conversation_history_limit=20,
        order_history_limit=5,
        product_context_limit=5,
    )

    assert SYSTEM_PROMPT in system_instruction
    assert "order-1" in system_instruction
    assert "Frozen Peas" in system_instruction

    # History mapped to Gemini roles ("assistant" -> "model"), oldest first,
    # then the new user message.
    assert contents[0] == {"role": "model", "content": "How can I help?"}
    assert contents[1] == {"role": "user", "content": "Where's my order?"}
    assert contents[-1] == {"role": "user", "content": "Where's my order?"}

    orders_client.get_recent_orders.assert_awaited_once_with(REGISTERED_CUSTOMER_ID, 5)


async def test_build_messages_skips_order_history_for_guest():
    session = await _fake_session_returning([])
    genai_client = _fake_genai_client()
    chat_client = _chat_client([])
    orders_client = _orders_client([])

    system_instruction, _contents = await build_messages(
        session=session,
        genai_client=genai_client,
        embedding_model="gemini-embedding-001",
        embedding_dimensions=1536,
        chat_client=chat_client,
        orders_client=orders_client,
        room_id=f"room_{GUEST_ID}",
        sender_id=GUEST_ID,
        sender_role="guest",
        customer_message="What's in stock?",
        conversation_history_limit=20,
        order_history_limit=5,
        product_context_limit=5,
    )

    orders_client.get_recent_orders.assert_not_awaited()
    assert "Customer's recent orders" not in system_instruction
