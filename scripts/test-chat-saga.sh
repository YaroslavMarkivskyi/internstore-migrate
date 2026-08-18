#!/usr/bin/env bash
# K8s counterpart: scripts/k8s/test-chat-saga.sh (STR-145). If you fix a
# bug in this script, check whether the same bug exists there too -- see
# STR-151, which found fixes made in one copy that were never ported to
# the other.
#
# End-to-end verification of the Chat service (STR-128) through the real
# gateway, real Firebase-issued tokens, real Redis pub/sub, and a real
# Postgres-backed outbox -> Kafka -> Notifications -> Mailpit hop — not
# mocked anywhere.
#
# Covers:
#   1. Customer connects, sends a message with no admin online.
#   2. Admin connects, receives history + that message, replies.
#   3. Customer receives the admin's reply (Approach 1 round-trip).
#   4. Customer and admin both disconnect.
#   5. Customer reconnects and sends a fresh message with no admin online
#      again (notification_sent_at was reset when the admin joined in step
#      2) -> verifies Mailpit received the UnreadMessageReceived email.
#
# Requires: curl, jq, docker compose, and services/chat's own uv-managed
# venv (reused here for its `websockets` dependency — pulled in
# transitively by uvicorn[standard] — rather than requiring a second,
# separate Python environment on the host just for this script).
#
# Run after `docker compose up -d --build` (needs chat-db, chat, redis,
# kafka, kafka-topic-init, mailpit, notifications, nginx, firebase-emulator,
# auth-backend all healthy).
set -euo pipefail

FIREBASE_AUTH_EMULATOR_URL="http://localhost:9099"
AUTH_BACKEND_URL="http://localhost:3000"
MAILPIT_URL="http://localhost:8025"
FIREBASE_PROJECT_ID="internstore-dev"
CURL="curl -sk"
CHAT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/services/chat"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

login() {
  curl -sf -X POST "$FIREBASE_AUTH_EMULATOR_URL/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$1\",\"password\":\"$2\",\"returnSecureToken\":true}" | jq -r .idToken
}

sub_of() {
  # $1 = bearer token — auth-backend's /me is the simplest way to get the
  # Firebase uid without decoding the JWT ourselves.
  $CURL "$AUTH_BACKEND_URL/me" -H "Authorization: Bearer $1" | jq -r .sub
}

find_message_id() {
  curl -sf "$MAILPIT_URL/api/v1/search?query=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote('to:' + sys.argv[1]))" "$1")" \
    | jq -r --arg subject "$2" '.messages[] | select(.Subject | contains($subject)) | .ID' | head -n1
}

CUSTOMER_TOKEN=$(login "customer@example.com" "Customer123")
ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$CUSTOMER_TOKEN" != "null" ] || fail "customer login did not return an access token"
[ "$ADMIN_TOKEN" != "null" ] || fail "admin login did not return an access token"

CUSTOMER_SUB=$(sub_of "$CUSTOMER_TOKEN")
[ -n "$CUSTOMER_SUB" ] && [ "$CUSTOMER_SUB" != "null" ] || fail "could not resolve customer sub via /me"
ROOM_ID="room_${CUSTOMER_SUB}"

echo "=== Real WebSocket round-trip: customer <-> admin, both directions ==="

(
  cd "$CHAT_DIR"
  CUSTOMER_TOKEN="$CUSTOMER_TOKEN" ADMIN_TOKEN="$ADMIN_TOKEN" ROOM_ID="$ROOM_ID" \
    uv run python3 - <<'PYEOF'
import asyncio
import json
import os
import ssl
import sys

import websockets

CUSTOMER_TOKEN = os.environ["CUSTOMER_TOKEN"]
ADMIN_TOKEN = os.environ["ADMIN_TOKEN"]
ROOM_ID = os.environ["ROOM_ID"]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def url(token: str) -> str:
    return f"wss://localhost:8443/ws/room/{ROOM_ID}?token={token}"


async def recv_json(ws, label: str) -> dict:
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
    except TimeoutError:
        print(f"FAIL: timed out waiting for {label}", flush=True)
        sys.exit(1)
    return json.loads(raw)


async def main() -> None:
    async with websockets.connect(url(CUSTOMER_TOKEN), ssl=SSL_CTX) as customer_ws:
        history = await recv_json(customer_ws, "customer history frame")
        assert history["type"] == "history", history
        print("PASS: customer connected, received history frame", flush=True)

        await customer_ws.send(json.dumps({"type": "message", "content": "Hello, I need help"}))
        customer_echo = await recv_json(customer_ws, "customer's own message echo")
        assert customer_echo["content"] == "Hello, I need help", customer_echo
        print("PASS: customer sent message, received own echo (Approach 1 confirmation)", flush=True)

        async with websockets.connect(url(ADMIN_TOKEN), ssl=SSL_CTX) as admin_ws:
            admin_history = await recv_json(admin_ws, "admin history frame")
            assert admin_history["type"] == "history"
            assert any(m["content"] == "Hello, I need help" for m in admin_history["messages"]), admin_history
            print("PASS: admin connected, history replay includes the customer's message", flush=True)

            await admin_ws.send(json.dumps({"type": "message", "content": "Hi, how can I help?"}))
            admin_echo = await recv_json(admin_ws, "admin's own message echo")
            assert admin_echo["content"] == "Hi, how can I help?", admin_echo
            print("PASS: admin replied, received own echo", flush=True)

            customer_received = await recv_json(customer_ws, "customer receiving admin's reply")
            assert customer_received["content"] == "Hi, how can I help?", customer_received
            assert customer_received["sender_type"] == "admin"
            print("PASS: customer received admin's reply via Redis pub/sub round-trip", flush=True)

    print("PASS: customer and admin both disconnected cleanly", flush=True)

    # Second round: no admin online (the one above already disconnected) —
    # notification_sent_at was reset to NULL when that admin connected, so
    # this fresh message should stage a new UnreadMessageReceived event.
    async with websockets.connect(url(CUSTOMER_TOKEN), ssl=SSL_CTX) as customer_ws:
        await recv_json(customer_ws, "customer history frame (second connect)")
        await customer_ws.send(json.dumps({"type": "message", "content": "Still there?"}))
        await recv_json(customer_ws, "customer's own echo (second message)")
        print("PASS: customer reconnected and sent a message with no admin online", flush=True)


asyncio.run(main())
PYEOF
)

echo
echo "=== Offline-admin notification -> UnreadMessageReceived -> Mailpit ==="

MESSAGE_ID=""
ELAPSED=0
while [ "$ELAPSED" -lt 30 ]; do
  MESSAGE_ID=$(find_message_id "ops@internstore.local" "unread message")
  [ -n "$MESSAGE_ID" ] && break
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done
[ -n "$MESSAGE_ID" ] || fail "no UnreadMessageReceived email appeared in Mailpit within 30s"
pass "UnreadMessageReceived -> (real outbox+Kafka) -> Notifications -> (real SMTP) -> email visible in Mailpit (took ~${ELAPSED}s)"

MESSAGE=$(curl -sf "$MAILPIT_URL/api/v1/message/$MESSAGE_ID")
echo "$MESSAGE" | jq -r .Text | grep -qi "$CUSTOMER_SUB" || fail "email body did not mention the sender: $(echo "$MESSAGE" | jq -r .Text)"
pass "email content verified via Mailpit REST API: mentions the customer as sender"

echo
echo "All chat saga verification checks passed against the real gateway, Redis, and Kafka broker."
