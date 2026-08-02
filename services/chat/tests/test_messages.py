import json
from datetime import datetime, timedelta, timezone

from chat.models import Message, Room, SenderType

ROOM_ID = "room_11111111-1111-1111-1111-111111111111"


def connect(ws_client, room_id: str, token: str):
    return ws_client.websocket_connect(f"/ws/room/{room_id}", headers={"x-internal-token": token})


async def _seed_messages(app, count: int) -> list[str]:
    ids = []
    async with app.state.session_factory() as session:
        session.add(Room(id=ROOM_ID))
        await session.flush()
        base = datetime.now(timezone.utc)
        for i in range(count):
            message = Message(
                room_id=ROOM_ID,
                sender_type=SenderType.CUSTOMER,
                sender_id="11111111-1111-1111-1111-111111111111",
                content=f"message {i}",
                created_at=base + timedelta(seconds=i),
            )
            session.add(message)
            await session.flush()
            ids.append(str(message.id))
        await session.commit()
    return ids


async def test_pagination_cursor_walks_backwards_through_history(app, client, admin_token):
    ids = await _seed_messages(app, 5)

    first_page = await client.get(
        f"/rooms/{ROOM_ID}/messages", params={"limit": 2}, headers={"x-internal-token": admin_token}
    )
    assert first_page.status_code == 200
    first_contents = [m["content"] for m in first_page.json()["messages"]]
    assert first_contents == ["message 4", "message 3"]

    second_page = await client.get(
        f"/rooms/{ROOM_ID}/messages",
        params={"limit": 2, "before": ids[3]},
        headers={"x-internal-token": admin_token},
    )
    second_contents = [m["content"] for m in second_page.json()["messages"]]
    assert second_contents == ["message 2", "message 1"]


async def test_history_replay_on_connect_for_registered_users(app, ws_client, customer_token):
    await _seed_messages(app, 3)

    with connect(ws_client, ROOM_ID, customer_token) as ws:
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "history"
        contents = [m["content"] for m in frame["messages"]]
        # Oldest-first for display.
        assert contents == ["message 0", "message 1", "message 2"]


async def test_guest_gets_no_history_replay(app, ws_client, guest_token):
    with connect(ws_client, "room_guest-session-1", guest_token) as ws:
        ws.send_text(json.dumps({"type": "message", "content": "first"}))
        # The only frame a guest should receive is the echo of its own
        # message — no history replay is sent for guests.
        frame = json.loads(ws.receive_text())
        assert frame["content"] == "first"
