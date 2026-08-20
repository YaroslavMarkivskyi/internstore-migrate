from sqlalchemy import select

from chat.models import OutboxEvent, Room
from tests.conftest import mint_internal_token, ws_connect as connect

CUSTOMER_SUB = "11111111-1111-1111-1111-111111111111"
ROOM_ID = f"room_{CUSTOMER_SUB}"
OTHER_ROOM_ID = "room_22222222-2222-2222-2222-222222222222"


async def _outbox_events(app, event_type: str) -> list[OutboxEvent]:
    async with app.state.session_factory() as session:
        result = await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == event_type))
        return list(result.scalars().all())


async def _create_room(ws_client, room_id: str, token: str) -> None:
    with connect(ws_client, room_id, token):
        pass


async def test_patch_mode_sets_db_and_redis(app, ws_client, client, customer_token):
    await _create_room(ws_client, ROOM_ID, customer_token)

    response = await client.patch(
        f"/rooms/{ROOM_ID}/mode",
        json={"mode": "human"},
        headers=customer_token,
    )
    assert response.status_code == 200
    assert response.json() == {"mode": "human"}

    async with app.state.session_factory() as session:
        room = await session.get(Room, ROOM_ID)
        assert room.ai_mode is False

    assert await app.state.redis.get(f"chat:{ROOM_ID}:mode") == "human"


async def test_get_mode_reflects_current_state(app, ws_client, client, customer_token):
    await _create_room(ws_client, ROOM_ID, customer_token)

    response = await client.get(f"/rooms/{ROOM_ID}/mode", headers=customer_token)
    assert response.status_code == 200
    assert response.json() == {"mode": "ai"}

    await client.patch(
        f"/rooms/{ROOM_ID}/mode", json={"mode": "human"}, headers=customer_token
    )

    response = await client.get(f"/rooms/{ROOM_ID}/mode", headers=customer_token)
    assert response.json() == {"mode": "human"}


async def test_customer_cannot_toggle_other_rooms(app, ws_client, client, customer_token, admin_token):
    await _create_room(ws_client, OTHER_ROOM_ID, admin_token)

    response = await client.patch(
        f"/rooms/{OTHER_ROOM_ID}/mode",
        json={"mode": "human"},
        headers=customer_token,
    )
    assert response.status_code == 403


async def test_admin_can_toggle_any_room(app, ws_client, client, customer_token, admin_token):
    await _create_room(ws_client, ROOM_ID, customer_token)

    response = await client.patch(
        f"/rooms/{ROOM_ID}/mode",
        json={"mode": "human"},
        headers=admin_token,
    )
    assert response.status_code == 200
    assert response.json() == {"mode": "human"}


async def test_switching_to_human_stages_admin_requested_event(app, ws_client, client, customer_token):
    await _create_room(ws_client, ROOM_ID, customer_token)

    await client.patch(
        f"/rooms/{ROOM_ID}/mode", json={"mode": "human"}, headers=customer_token
    )

    events = await _outbox_events(app, "AdminRequested")
    assert len(events) == 1
    assert events[0].payload["room_id"] == ROOM_ID


async def test_switching_to_ai_stages_ai_mode_enabled_event(app, ws_client, client, customer_token):
    await _create_room(ws_client, ROOM_ID, customer_token)
    await client.patch(
        f"/rooms/{ROOM_ID}/mode", json={"mode": "human"}, headers=customer_token
    )

    await client.patch(f"/rooms/{ROOM_ID}/mode", json={"mode": "ai"}, headers=customer_token)

    events = await _outbox_events(app, "AIModeEnabled")
    assert len(events) == 1
    assert events[0].payload["room_id"] == ROOM_ID


async def test_assistant_can_post_internal_message(app, ws_client, client, customer_token):
    await _create_room(ws_client, ROOM_ID, customer_token)
    assistant_token = mint_internal_token(sub="ai-assistant", role="assistant")

    response = await client.post(
        f"/rooms/{ROOM_ID}/messages",
        json={"content": "Your order shipped yesterday."},
        headers=assistant_token,
    )
    assert response.status_code == 201
    assert response.json()["sender_type"] == "assistant"

    messages_response = await client.get(
        f"/rooms/{ROOM_ID}/messages", headers=mint_internal_token(sub="a", role="admin")
    )
    contents = [m["content"] for m in messages_response.json()["messages"]]
    assert "Your order shipped yesterday." in contents
