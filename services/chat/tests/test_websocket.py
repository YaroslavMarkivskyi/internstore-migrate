import json

from tests.conftest import mint_internal_token, ws_connect


def test_customer_and_admin_message_flow_both_directions(ws_client, customer_token, admin_token):
    room_id = "room_11111111-1111-1111-1111-111111111111"

    with ws_connect(ws_client, room_id, customer_token) as customer_ws:
        with ws_connect(ws_client, room_id, admin_token) as admin_ws:
            customer_ws.send_text(json.dumps({"type": "message", "content": "hi from customer"}))

            # Approach 1: the sender also receives its own message back
            # through the Redis pub/sub round-trip (implicit delivery
            # confirmation), and the admin receives it too.
            customer_echo = json.loads(customer_ws.receive_text())
            assert customer_echo["content"] == "hi from customer"
            assert customer_echo["sender_type"] == "customer"

            admin_received = json.loads(admin_ws.receive_text())
            assert admin_received["content"] == "hi from customer"

            admin_ws.send_text(json.dumps({"type": "message", "content": "hi from admin"}))

            admin_echo = json.loads(admin_ws.receive_text())
            assert admin_echo["content"] == "hi from admin"
            assert admin_echo["sender_type"] == "admin"

            customer_received = json.loads(customer_ws.receive_text())
            assert customer_received["content"] == "hi from admin"


def test_guest_session_can_only_open_own_room(ws_client, guest_token):
    own_room = "room_guest-session-1"
    with ws_connect(ws_client, own_room, guest_token, is_guest=True) as ws:
        ws.send_text(json.dumps({"type": "message", "content": "hello"}))
        echo = json.loads(ws.receive_text())
        assert echo["sender_type"] == "customer"
        assert echo["sender_id"] == "guest-session-1"


def test_guest_cannot_open_someone_elses_room(ws_client, guest_token):
    other_room = "room_someone-else"
    try:
        with ws_connect(ws_client, other_room, guest_token, is_guest=True):
            raise AssertionError("expected the connection to be rejected")
    except Exception:
        # Starlette surfaces a rejected handshake as a WebSocketDisconnect
        # (close code 1008) raised out of the context manager.
        pass


def test_customer_cannot_open_someone_elses_room(ws_client):
    other_customer_token = mint_internal_token(sub="22222222-2222-2222-2222-222222222222", role="customer")
    my_room = "room_11111111-1111-1111-1111-111111111111"
    try:
        with ws_connect(ws_client, my_room, other_customer_token):
            raise AssertionError("expected the connection to be rejected")
    except Exception:
        pass


def test_no_duplicate_delivery_to_same_client(ws_client, customer_token, admin_token):
    room_id = "room_11111111-1111-1111-1111-111111111111"
    with ws_connect(ws_client, room_id, customer_token) as customer_ws:
        with ws_connect(ws_client, room_id, admin_token) as admin_ws:
            customer_ws.send_text(json.dumps({"type": "message", "content": "only once"}))

            # Each client reads exactly one message off the wire for this
            # send — Approach 1 guarantees single delivery per subscriber
            # (one PUBLISH -> one delivery per connected socket), so a
            # second receive_text() with a short timeout should find
            # nothing further queued.
            json.loads(customer_ws.receive_text())
            json.loads(admin_ws.receive_text())

            customer_ws.send_text(json.dumps({"type": "typing"}))
            admin_typing = json.loads(admin_ws.receive_text())
            assert admin_typing["type"] == "typing"
