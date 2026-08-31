"""STR-XXX: POST /rooms/{id}/messages/stream — the AI Assistant streams its
reply here chunk by chunk; each chunk fans out to the room's WebSocket
clients, and only the final `done` call persists the assembled message."""

import json

from chat.models import Message, SenderType
from sqlalchemy import select
from tests.conftest import mint_internal_token, ws_connect

CUSTOMER_SUB = "11111111-1111-1111-1111-111111111111"
ROOM_ID = f"room_{CUSTOMER_SUB}"


def _assistant_token() -> dict[str, str]:
    return mint_internal_token(sub="ai-assistant", role="assistant")


async def _persisted_contents(app) -> list[str]:
    async with app.state.session_factory() as session:
        rows = await session.execute(select(Message).where(Message.sender_type == SenderType.ASSISTANT))
        return [m.content for m in rows.scalars().all()]


async def test_deltas_are_broadcast_and_only_done_persists(app, ws_client, client, customer_token):
    stream_id = "stream-1"
    with ws_connect(ws_client, ROOM_ID, customer_token) as ws:
        r1 = await client.post(
            f"/rooms/{ROOM_ID}/messages/stream",
            json={"stream_id": stream_id, "delta": "Added the Gouda"},
            headers=_assistant_token(),
        )
        assert r1.status_code == 202
        first = json.loads(ws.receive_text())
        assert first == {
            "type": "message_delta",
            "room_id": ROOM_ID,
            "stream_id": stream_id,
            "delta": "Added the Gouda",
        }

        await client.post(
            f"/rooms/{ROOM_ID}/messages/stream",
            json={"stream_id": stream_id, "delta": " — 1 in your cart."},
            headers=_assistant_token(),
        )
        json.loads(ws.receive_text())

        # Nothing persisted yet.
        assert await _persisted_contents(app) == []

        r_done = await client.post(
            f"/rooms/{ROOM_ID}/messages/stream",
            json={"stream_id": stream_id, "done": True, "content": "Added the Gouda — 1 in your cart."},
            headers=_assistant_token(),
        )
        assert r_done.status_code == 202
        done = json.loads(ws.receive_text())
        assert done["type"] == "message_done"
        assert done["stream_id"] == stream_id
        assert done["content"] == "Added the Gouda — 1 in your cart."
        assert done["sender_type"] == "assistant"

    assert await _persisted_contents(app) == ["Added the Gouda — 1 in your cart."]


async def test_reset_frame_is_broadcast_and_persists_nothing(app, ws_client, client, customer_token):
    with ws_connect(ws_client, ROOM_ID, customer_token) as ws:
        await client.post(
            f"/rooms/{ROOM_ID}/messages/stream",
            json={"stream_id": "s2", "delta": "Let me check"},
            headers=_assistant_token(),
        )
        json.loads(ws.receive_text())

        await client.post(
            f"/rooms/{ROOM_ID}/messages/stream",
            json={"stream_id": "s2", "reset": True},
            headers=_assistant_token(),
        )
        reset = json.loads(ws.receive_text())
        assert reset == {"type": "message_reset", "room_id": ROOM_ID, "stream_id": "s2"}

    assert await _persisted_contents(app) == []


async def test_done_with_empty_content_persists_nothing(app, ws_client, client, customer_token):
    with ws_connect(ws_client, ROOM_ID, customer_token) as ws:
        await client.post(
            f"/rooms/{ROOM_ID}/messages/stream",
            json={"stream_id": "s3", "done": True, "content": "   "},
            headers=_assistant_token(),
        )
        done = json.loads(ws.receive_text())
        assert done["type"] == "message_done"
        assert done["content"] == ""

    assert await _persisted_contents(app) == []


async def test_stream_to_unknown_room_is_404(client):
    resp = await client.post(
        "/rooms/room_does-not-exist/messages/stream",
        json={"stream_id": "s4", "delta": "hi"},
        headers=_assistant_token(),
    )
    assert resp.status_code == 404
