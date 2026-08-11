import json

from sqlalchemy import select

from chat.models import OutboxEvent, Room
from tests.conftest import ws_connect as connect

ROOM_ID = "room_11111111-1111-1111-1111-111111111111"


async def _outbox_events(app, event_type: str = "UnreadMessageReceived") -> list[OutboxEvent]:
    async with app.state.session_factory() as session:
        result = await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == event_type))
        return list(result.scalars().all())


async def test_customer_message_sent_carries_sender_role(app, ws_client, customer_token):
    """STR-148: ai-assistant used to guess "is this a registered customer"
    from whether sender_id merely looked like a UUID — broken, since guest
    session ids are uuid4() too, which silently misclassified every guest
    as a customer and left guests with no AI reply at all. sender_role is
    now included explicitly so no downstream consumer has to guess."""
    with connect(ws_client, ROOM_ID, customer_token) as ws:
        ws.send_text(json.dumps({"type": "message", "content": "hello?"}))
        ws.receive_text()

    events = await _outbox_events(app, "CustomerMessageSent")
    assert len(events) == 1
    assert events[0].payload["sender_role"] == "customer"


async def test_first_message_with_no_admin_online_stages_outbox_event(app, ws_client, customer_token):
    with connect(ws_client, ROOM_ID, customer_token) as ws:
        ws.send_text(json.dumps({"type": "message", "content": "hello?"}))
        ws.receive_text()

    events = await _outbox_events(app)
    assert len(events) == 1
    assert events[0].payload["sender_name"] == "11111111-1111-1111-1111-111111111111"

    async with app.state.session_factory() as session:
        room = await session.get(Room, ROOM_ID)
        assert room.notification_sent_at is not None


async def test_subsequent_messages_do_not_re_stage(app, ws_client, customer_token):
    with connect(ws_client, ROOM_ID, customer_token) as ws:
        ws.send_text(json.dumps({"type": "message", "content": "first"}))
        ws.receive_text()
        ws.send_text(json.dumps({"type": "message", "content": "second"}))
        ws.receive_text()

    events = await _outbox_events(app)
    assert len(events) == 1


async def test_admin_joining_resets_notification_state(app, ws_client, customer_token, admin_token):
    with connect(ws_client, ROOM_ID, customer_token) as customer_ws:
        customer_ws.send_text(json.dumps({"type": "message", "content": "first"}))
        customer_ws.receive_text()

    with connect(ws_client, ROOM_ID, admin_token):
        pass

    async with app.state.session_factory() as session:
        room = await session.get(Room, ROOM_ID)
        assert room.notification_sent_at is None

    # A fresh round of offline messages after the admin has come and gone
    # can notify again.
    with connect(ws_client, ROOM_ID, customer_token) as customer_ws:
        customer_ws.send_text(json.dumps({"type": "message", "content": "second round"}))
        customer_ws.receive_text()

    events = await _outbox_events(app)
    assert len(events) == 2
