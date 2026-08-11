"""STR-146: guests get no shopping-agent access. Two independent checks —
Chat is expected to never call POST /agent/shopping for a guest sender (see
services/chat/src/chat/ws/room.py), but this endpoint fails closed on its
own too, and the Kafka-driven path guests still use never touches the
tool-calling loop or the MCP Gateway."""

from unittest.mock import AsyncMock

from ai_assistant.consumers.chat_events import handle_customer_message_sent

ROOM_ID = "room_guest-session-1"


async def test_shopping_agent_endpoint_rejects_a_guest_token(client, guest_token):
    resp = await client.post(
        "/agent/shopping",
        json={"room_id": ROOM_ID, "sender_id": "guest-session-1", "message": "find me a cheese"},
        headers={"X-Internal-Token": guest_token},
    )

    assert resp.status_code == 403


async def test_shopping_agent_endpoint_rejects_missing_token(client):
    resp = await client.post(
        "/agent/shopping",
        json={"room_id": ROOM_ID, "sender_id": "guest-session-1", "message": "find me a cheese"},
    )

    assert resp.status_code == 401


async def test_guest_message_over_kafka_never_reaches_the_tool_calling_loop(monkeypatch):
    # Guests still get the original, tool-less generate_reply path over the
    # chat-events consumer (unchanged from before STR-146) — this proves
    # that path never imports or calls into the MCP Gateway/ReAct loop at
    # all, regardless of what the guest asks for.
    #
    # STR-148: sender_id is deliberately a plain UUID here (matching a real
    # guest session id — see auth-backend's GuestSessionStore), not a
    # human-readable "guest-session-1"-style string. The old
    # is_registered_customer(sender_id) shape-guess this dispatch used to
    # rely on happened to work on non-UUID-looking ids like that one, which
    # is exactly why the real bug (guest ids are uuid4() too) went
    # unnoticed by this test suite until live verification caught it.
    import ai_assistant.consumers.chat_events as chat_events_module

    called_generate_reply = AsyncMock(return_value="Here's some general help.")
    monkeypatch.setattr(chat_events_module, "generate_reply", called_generate_reply)

    class _Settings:
        ai_mode_default = "ai"
        ai_rate_limit = 10
        ai_rate_limit_window_seconds = 3600
        embedding_model = "text-embedding-3-small"
        chat_model = "gpt-4o"
        max_response_tokens = 500
        conversation_history_limit = 20
        order_history_limit = 5
        product_context_limit = 5

    import fakeredis

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    chat_client = AsyncMock()
    chat_client.get_recent_messages = AsyncMock(return_value=[])
    orders_client = AsyncMock()

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, _stmt):
            return iter([])  # no similar products -- irrelevant to this test

    def session_factory():
        return _FakeSession()

    await handle_customer_message_sent(
        session_factory=session_factory,
        redis=redis,
        openai_client=AsyncMock(),
        chat_client=chat_client,
        orders_client=orders_client,
        settings=_Settings(),
        payload={
            "room_id": ROOM_ID,
            "sender_id": "22222222-2222-2222-2222-222222222222",
            "sender_role": "guest",
            "content": "add cheese to my cart",
        },
    )

    called_generate_reply.assert_awaited_once()
    orders_client.get_recent_orders.assert_not_awaited()  # guest has no order history either


async def test_registered_customer_message_over_kafka_is_skipped_entirely():
    # STR-146: customers are handled synchronously via POST /agent/shopping
    # instead (see main.py) -- the Kafka consumer must do nothing for them,
    # not fall back to the old tool-less reply either.
    class _Settings:
        ai_mode_default = "ai"
        ai_rate_limit = 10
        ai_rate_limit_window_seconds = 3600

    openai_client = AsyncMock()
    chat_client = AsyncMock()

    await handle_customer_message_sent(
        session_factory=AsyncMock(),
        redis=AsyncMock(),
        openai_client=openai_client,
        chat_client=chat_client,
        orders_client=AsyncMock(),
        settings=_Settings(),
        payload={
            "room_id": "room_11111111-1111-1111-1111-111111111111",
            "sender_id": "11111111-1111-1111-1111-111111111111",
            "sender_role": "customer",
            "content": "add cheese to my cart",
        },
    )

    openai_client.chat.completions.create.assert_not_awaited()
    chat_client.post_message.assert_not_awaited()
