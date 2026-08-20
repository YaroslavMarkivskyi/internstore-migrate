import json

from tests.conftest import ws_connect

CUSTOMER_ROOM = "room_11111111-1111-1111-1111-111111111111"


async def test_lazy_room_creation_on_first_connect(app, ws_client, client, customer_token, admin_token):
    with ws_connect(ws_client, CUSTOMER_ROOM, customer_token):
        pass

    response = await client.get("/rooms", headers=admin_token)
    assert response.status_code == 200
    room_ids = [room["id"] for room in response.json()["rooms"]]
    assert CUSTOMER_ROOM in room_ids


async def test_unread_count_when_no_admin_present(app, ws_client, client, customer_token, admin_token):
    with ws_connect(ws_client, CUSTOMER_ROOM, customer_token) as customer_ws:
        customer_ws.send_text(json.dumps({"type": "message", "content": "anyone there?"}))
        echo = json.loads(customer_ws.receive_text())
        assert echo["content"] == "anyone there?"

    response = await client.get("/rooms", headers=admin_token)
    room = next(r for r in response.json()["rooms"] if r["id"] == CUSTOMER_ROOM)
    assert room["unread_count"] == 1
    assert room["last_message"] == "anyone there?"


async def test_delete_room_removes_room_and_messages(app, ws_client, client, customer_token, admin_token):
    with ws_connect(ws_client, CUSTOMER_ROOM, customer_token) as customer_ws:
        customer_ws.send_text(json.dumps({"type": "message", "content": "hello"}))
        customer_ws.receive_text()

    delete_response = await client.delete(f"/rooms/{CUSTOMER_ROOM}", headers=admin_token)
    assert delete_response.status_code == 204

    messages_response = await client.get(
        f"/rooms/{CUSTOMER_ROOM}/messages", headers=admin_token
    )
    assert messages_response.status_code == 404
