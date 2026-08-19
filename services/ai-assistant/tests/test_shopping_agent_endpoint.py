from types import SimpleNamespace
from unittest.mock import AsyncMock

from ai_assistant.agent import RATE_LIMIT_MESSAGE

ROOM_ID = "room_11111111-1111-1111-1111-111111111111"
SENDER_ID = "11111111-1111-1111-1111-111111111111"


def _response(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text, function_calls=[], candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[]))])


async def test_customer_message_runs_the_agent_and_posts_the_reply(client, app, customer_token):
    app.state.mcp_client.list_tools = AsyncMock(return_value=[])
    app.state.genai_client.aio.models.generate_content = AsyncMock(
        return_value=_response("Added 2x Gouda to your cart — 3 items now, $34.50 total.")
    )

    resp = await client.post(
        "/agent/shopping",
        json={"room_id": ROOM_ID, "sender_id": "customer-1", "message": "add it to my cart"},
        headers={"X-Internal-Token": customer_token},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    app.state.chat_client.post_message.assert_awaited_once_with(
        ROOM_ID, "Added 2x Gouda to your cart — 3 items now, $34.50 total."
    )


async def test_customer_message_fetches_and_forwards_room_history(client, app, customer_token):
    """STR-148 regression: POST /agent/shopping must fetch the room's prior
    messages and pass them into the ReAct loop — without it, the agent
    treats every message as the start of a brand new conversation."""
    app.state.chat_client.get_recent_messages = AsyncMock(
        return_value=[{"sender_type": "customer", "content": "find me a gouda under $20"}]
    )
    app.state.mcp_client.list_tools = AsyncMock(return_value=[])
    app.state.genai_client.aio.models.generate_content = AsyncMock(return_value=_response("Added it to your cart."))

    resp = await client.post(
        "/agent/shopping",
        json={"room_id": ROOM_ID, "sender_id": "customer-1", "message": "add it to my cart"},
        headers={"X-Internal-Token": customer_token},
    )

    assert resp.status_code == 200
    app.state.chat_client.get_recent_messages.assert_awaited_once_with(ROOM_ID, app.state.settings.conversation_history_limit)
    sent_contents = app.state.genai_client.aio.models.generate_content.call_args.kwargs["contents"]
    assert any(c.role == "user" and c.parts[0].text == "find me a gouda under $20" for c in sent_contents)


async def test_human_mode_room_skips_the_agent_entirely(client, app, customer_token):
    await app.state.redis.set(f"chat:{ROOM_ID}:mode", "human")

    resp = await client.post(
        "/agent/shopping",
        json={"room_id": ROOM_ID, "sender_id": "customer-1", "message": "add it to my cart"},
        headers={"X-Internal-Token": customer_token},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "skipped"}
    app.state.genai_client.aio.models.generate_content.assert_not_awaited()
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
