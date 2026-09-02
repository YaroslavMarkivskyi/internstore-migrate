"""The guest support path: signed-out chat-widget visitors, handled over the
chat-events Kafka consumer by the ADK `guest_assistant` agent.

Guests get no shopping-agent access. Independent checks:
  - POST /agent/shopping fails closed on a guest token (Chat also never
    calls it for a guest — see services/chat/src/chat/ws/room.py);
  - the Kafka path mints a `guest`-role token, so the Gateway pins it to the
    read-only guest tool tier (mcp_gateway/authz._GUEST_TIER) — no cart, no
    order history;
  - registered customers are skipped entirely here (handled synchronously
    via POST /agent/shopping instead).
"""

from unittest.mock import AsyncMock

import fakeredis
import jwt
from google.adk.sessions import InMemorySessionService

import ai_assistant.consumers.chat_events as chat_events_module
from ai_assistant.consumers.chat_events import handle_customer_message_sent
from tests.adk_fakes import fake_agent_stream
from tests.conftest import INTERNAL_TOKEN_SECRET, ISSUER

ROOM_ID = "room_guest-session-1"
GUEST_ID = "22222222-2222-2222-2222-222222222222"


class _Settings:
    internal_token_secret = INTERNAL_TOKEN_SECRET
    ai_mode_default = "ai"
    ai_rate_limit = 10
    ai_rate_limit_window_seconds = 3600
    conversation_history_limit = 20
    max_react_iterations = 5


def _chat_client() -> AsyncMock:
    client = AsyncMock()
    client.get_recent_messages = AsyncMock(return_value=[])
    return client


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


async def test_guest_message_runs_the_guest_agent_with_a_guest_scoped_token(monkeypatch):
    fake = fake_agent_stream("Here's what I found.")
    monkeypatch.setattr(chat_events_module, "run_agent_stream", fake)

    minted: list[str] = []
    real_mint = chat_events_module.mint_internal_token
    monkeypatch.setattr(
        chat_events_module,
        "mint_internal_token",
        lambda *a, **kw: minted.append(real_mint(*a, **kw)) or minted[-1],
    )

    chat_client = _chat_client()

    await handle_customer_message_sent(
        redis=fakeredis.aioredis.FakeRedis(decode_responses=True),
        session_service=InMemorySessionService(),
        guest_runner=AsyncMock(),
        chat_client=chat_client,
        settings=_Settings(),
        payload={
            "room_id": ROOM_ID,
            "sender_id": GUEST_ID,
            "sender_role": "guest",
            "content": "add cheese to my cart",
        },
    )

    # The guest agent produced the reply, streamed + persisted via Chat.
    assert fake.calls and fake.calls[0]["author"] == "guest_assistant"
    chat_client.stream_done.assert_awaited_once()

    # The token minted for the MCP fan-out carries the guest's own id and
    # role — the Gateway maps `guest` to the no-cart, no-orders tool tier.
    claims = jwt.decode(minted[-1], INTERNAL_TOKEN_SECRET, algorithms=["HS256"], issuer=ISSUER)
    assert claims["sub"] == GUEST_ID and claims["role"] == "guest"


async def test_registered_customer_message_is_skipped_entirely(monkeypatch):
    fake = fake_agent_stream("should not run")
    monkeypatch.setattr(chat_events_module, "run_agent_stream", fake)
    chat_client = _chat_client()

    await handle_customer_message_sent(
        redis=AsyncMock(),
        session_service=InMemorySessionService(),
        guest_runner=AsyncMock(),
        chat_client=chat_client,
        settings=_Settings(),
        payload={
            "room_id": "room_11111111-1111-1111-1111-111111111111",
            "sender_id": "11111111-1111-1111-1111-111111111111",
            "sender_role": "customer",
            "content": "add cheese to my cart",
        },
    )

    assert fake.calls == []
    chat_client.stream_done.assert_not_awaited()
    chat_client.post_message.assert_not_awaited()
