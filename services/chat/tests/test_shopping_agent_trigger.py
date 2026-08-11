"""STR-146: Chat forwards a registered customer's own internal-token to AI
Assistant's shopping ReAct loop on every customer message in a room — guests
never trigger this at all (no agent access for them, verified independently
by ai-assistant's own role check on POST /agent/shopping)."""

import json
import time

from tests.conftest import ws_connect as connect

ROOM_ID = "room_11111111-1111-1111-1111-111111111111"
GUEST_ROOM_ID = "room_guest-session-1"


def test_customer_message_notifies_the_shopping_agent_with_the_real_token(app, ws_client, customer_token):
    with connect(ws_client, ROOM_ID, customer_token) as ws:
        ws.send_text(json.dumps({"type": "message", "content": "find me a gouda under $20"}))
        ws.receive_text()

    time.sleep(0.05)  # let the fire-and-forget background task run

    app.state.ai_assistant_client.notify_shopping_agent.assert_awaited_once_with(
        room_id=ROOM_ID,
        sender_id="11111111-1111-1111-1111-111111111111",
        message="find me a gouda under $20",
        token=customer_token,
    )


def test_guest_message_never_notifies_the_shopping_agent(app, ws_client, guest_token):
    with connect(ws_client, GUEST_ROOM_ID, guest_token, is_guest=True) as ws:
        ws.send_text(json.dumps({"type": "message", "content": "find me a gouda under $20"}))
        ws.receive_text()

    time.sleep(0.05)

    app.state.ai_assistant_client.notify_shopping_agent.assert_not_awaited()


def test_admin_message_never_notifies_the_shopping_agent(app, ws_client, admin_token):
    with connect(ws_client, ROOM_ID, admin_token) as ws:
        ws.send_text(json.dumps({"type": "message", "content": "internal note"}))
        ws.receive_text()

    time.sleep(0.05)

    app.state.ai_assistant_client.notify_shopping_agent.assert_not_awaited()
