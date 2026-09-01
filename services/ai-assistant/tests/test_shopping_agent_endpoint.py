from unittest.mock import AsyncMock

from ai_assistant.agent import RATE_LIMIT_MESSAGE
from tests.adk_fakes import fake_agent_stream

ROOM_ID = "room_11111111-1111-1111-1111-111111111111"
SENDER_ID = "11111111-1111-1111-1111-111111111111"


async def test_customer_message_streams_the_reply_and_persists_it_on_done(client, app, customer_token, monkeypatch):
    monkeypatch.setattr(
        "ai_assistant.main.run_agent_stream",
        fake_agent_stream("Added 2x Gouda to your cart", " — 3 items now, $34.50 total."),
    )

    resp = await client.post(
        "/agent/shopping",
        json={"room_id": ROOM_ID, "sender_id": "customer-1", "message": "add it to my cart"},
        headers={"X-Internal-Token": customer_token},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    # Deltas streamed out, then the full assembled text persisted once.
    assert app.state.chat_client.stream_delta.await_count >= 1
    streamed = "".join(call.args[2] for call in app.state.chat_client.stream_delta.await_args_list)
    assert streamed == "Added 2x Gouda to your cart — 3 items now, $34.50 total."
    done_call = app.state.chat_client.stream_done.await_args
    assert done_call.args[0] == ROOM_ID
    assert done_call.args[2] == "Added 2x Gouda to your cart — 3 items now, $34.50 total."
    app.state.chat_client.post_message.assert_not_awaited()


async def test_customer_message_fetches_and_seeds_room_history(client, app, customer_token, monkeypatch):
    """STR-148 regression: POST /agent/shopping must fetch the room's prior
    messages and seed them into the agent's session — without it, the agent
    treats every message as the start of a brand new conversation."""
    app.state.chat_client.get_recent_messages = AsyncMock(
        return_value=[{"sender_type": "customer", "content": "find me a gouda under $20"}]
    )
    fake = fake_agent_stream("Added it to your cart.")
    monkeypatch.setattr("ai_assistant.main.run_agent_stream", fake)

    resp = await client.post(
        "/agent/shopping",
        json={"room_id": ROOM_ID, "sender_id": "customer-1", "message": "add it to my cart"},
        headers={"X-Internal-Token": customer_token},
    )

    assert resp.status_code == 200
    app.state.chat_client.get_recent_messages.assert_awaited_once_with(
        ROOM_ID, app.state.settings.conversation_history_limit
    )
    session_id = fake.calls[0]["session_id"]
    session = await app.state.adk_session_service.get_session(
        app_name="ai-assistant", user_id="customer-1", session_id=session_id
    )
    assert any(
        e.content and e.content.parts[0].text == "find me a gouda under $20" for e in session.events
    )


async def test_human_mode_room_skips_the_agent_entirely(client, app, customer_token, monkeypatch):
    fake = fake_agent_stream("should not run")
    monkeypatch.setattr("ai_assistant.main.run_agent_stream", fake)
    await app.state.redis.set(f"chat:{ROOM_ID}:mode", "human")

    resp = await client.post(
        "/agent/shopping",
        json={"room_id": ROOM_ID, "sender_id": "customer-1", "message": "add it to my cart"},
        headers={"X-Internal-Token": customer_token},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "skipped"}
    assert fake.calls == []
    app.state.chat_client.post_message.assert_not_awaited()


async def test_rate_limited_room_sends_final_message_and_switches_to_human(client, app, customer_token):
    await app.state.redis.set(f"chat:{ROOM_ID}:mode", "ai")
    await app.state.redis.set(f"chat:{ROOM_ID}:ai_count", 10)

    resp = await client.post(
        "/agent/shopping",
        json={"room_id": ROOM_ID, "sender_id": "customer-1", "message": "add it to my cart"},
        headers={"X-Internal-Token": customer_token},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "rate_limited"}
    app.state.chat_client.post_message.assert_awaited_once_with(ROOM_ID, RATE_LIMIT_MESSAGE)
    app.state.chat_client.set_mode.assert_awaited_once_with(ROOM_ID, "human")


async def test_token_sub_must_match_declared_sender_id(client, customer_token):
    resp = await client.post(
        "/agent/shopping",
        json={"room_id": ROOM_ID, "sender_id": "someone-else", "message": "add it to my cart"},
        headers={"X-Internal-Token": customer_token},
    )

    assert resp.status_code == 401
