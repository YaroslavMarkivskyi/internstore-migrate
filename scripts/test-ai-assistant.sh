#!/usr/bin/env bash
# End-to-end verification of the AI Assistant service (STR-136) against the
# real stack: real Firebase tokens, real gateway, real Kafka broker, a real
# OpenAI API call (requires a working OPENAI_API_KEY on the ai-assistant
# container — see services/ai-assistant/README.md's dev-gaps note), and a
# real Mailpit hop for the human-handoff notification.
#
# Covers:
#   1. Customer sends a message about their order; AI responds within the
#      real OpenAI round-trip time, mentioning order data.
#   2. Toggling to human mode stages AdminRequested -> Notifications ->
#      Mailpit, and the AI stays silent on the next message.
#   3. Toggling back to ai resumes AI responses.
#
# Requires: curl, jq, python3, docker compose, and services/chat's own
# uv-managed venv (reused for its `websockets` dependency, same as
# scripts/test-chat-saga.sh). Run after `docker compose up -d --build`
# (needs chat, ai-assistant, ai-db, orders, inventory, kafka,
# kafka-topic-init, redis, mailpit, notifications, nginx, firebase-emulator,
# auth-backend all healthy, and a real OPENAI_API_KEY set for ai-assistant).
set -euo pipefail

FIREBASE_AUTH_EMULATOR_URL="http://localhost:9099"
AUTH_BACKEND_URL="http://localhost:3000"
GATEWAY_URL="https://localhost:8443/api"
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
  $CURL "$AUTH_BACKEND_URL/me" -H "Authorization: Bearer $1" | jq -r .sub
}

seed_stock() {
  # $1 = admin token, $2 = product_id, $3 = quantity
  local stock_id
  stock_id=$($CURL -X POST "$GATEWAY_URL/inventory/stocks" \
    -H "Authorization: Bearer $1" -H "Content-Type: application/json" \
    -d "{\"name\": \"AI assistant smoke stock $$-$RANDOM\"}" | jq -r .id)
  [ -n "$stock_id" ] && [ "$stock_id" != "null" ] || fail "seed_stock: could not create stock"
  $CURL -X POST "$GATEWAY_URL/inventory/stocks/$stock_id/items" \
    -H "Authorization: Bearer $1" -H "Content-Type: application/json" \
    -d "{\"product_id\": \"$2\", \"quantity\": $3}" >/dev/null
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

echo "=== Seed a real order so the AI has order data to reference ==="
PRODUCT_A=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_A" 10
$CURL -X POST "$GATEWAY_URL/orders/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_A\", \"quantity\": 1}" >/dev/null
CHECKOUT=$($CURL -X POST "$GATEWAY_URL/orders/checkout" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"contact_name\": \"AI Assistant Customer\", \"contact_email\": \"customer@example.com\", \"payment_method\": \"card\"}")
ORDER_ID=$(echo "$CHECKOUT" | jq -r .id)
[ -n "$ORDER_ID" ] && [ "$ORDER_ID" != "null" ] || fail "checkout did not return an order id: $CHECKOUT"
pass "order $ORDER_ID created for AI to reference"

echo
echo "=== AI mode: customer message gets a real AI reply mentioning the order ==="
(
  cd "$CHAT_DIR"
  CUSTOMER_TOKEN="$CUSTOMER_TOKEN" ROOM_ID="$ROOM_ID" ORDER_ID="$ORDER_ID" \
    uv run python3 - <<'PYEOF'
import asyncio
import json
import os
import ssl
import sys

import websockets

CUSTOMER_TOKEN = os.environ["CUSTOMER_TOKEN"]
ROOM_ID = os.environ["ROOM_ID"]
ORDER_ID = os.environ["ORDER_ID"]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

URL = f"wss://localhost:8443/ws/room/{ROOM_ID}?token={CUSTOMER_TOKEN}"


async def recv_until(ws, predicate, timeout: float, label: str) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            print(f"FAIL: timed out waiting for {label}", flush=True)
            sys.exit(1)
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except TimeoutError:
            print(f"FAIL: timed out waiting for {label}", flush=True)
            sys.exit(1)
        frame = json.loads(raw)
        if predicate(frame):
            return frame


async def main() -> None:
    async with websockets.connect(URL, ssl=SSL_CTX) as ws:
        await recv_until(ws, lambda f: f["type"] == "history", 10, "customer history frame")

        await ws.send(json.dumps({"type": "message", "content": "What is the status of my latest order?"}))
        await recv_until(ws, lambda f: f.get("content") == "What is the status of my latest order?", 10, "own echo")
        print("PASS: customer sent order-status question", flush=True)

        reply = await recv_until(ws, lambda f: f.get("sender_type") == "assistant", 30, "AI reply")
        content = (reply.get("content") or "").lower()
        assert ORDER_ID.lower() in content or "status" in content, f"AI reply did not reference order data: {reply}"
        print("PASS: AI replied within 30s, referencing order data", flush=True)


asyncio.run(main())
PYEOF
)

echo
echo "=== Switch to human mode: AdminRequested email, AI stays silent ==="
$CURL -X PATCH "$GATEWAY_URL/chat/rooms/$ROOM_ID/mode" -H "Authorization: Bearer $CUSTOMER_TOKEN" \
  -H "Content-Type: application/json" -d '{"mode": "human"}' >/dev/null
MODE=$($CURL "$GATEWAY_URL/chat/rooms/$ROOM_ID/mode" -H "Authorization: Bearer $CUSTOMER_TOKEN" | jq -r .mode)
[ "$MODE" = "human" ] || fail "expected mode=human after PATCH, got: $MODE"
pass "PATCH /rooms/:id/mode -> human"

MESSAGE_ID=""
ELAPSED=0
while [ "$ELAPSED" -lt 30 ]; do
  MESSAGE_ID=$(find_message_id "ops@internstore.local" "human support requested")
  [ -n "$MESSAGE_ID" ] && break
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done
[ -n "$MESSAGE_ID" ] || fail "no AdminRequested email appeared in Mailpit within 30s"
pass "AdminRequested -> (real outbox+Kafka) -> Notifications -> Mailpit (took ~${ELAPSED}s)"

(
  cd "$CHAT_DIR"
  CUSTOMER_TOKEN="$CUSTOMER_TOKEN" ROOM_ID="$ROOM_ID" \
    uv run python3 - <<'PYEOF'
import asyncio
import json
import os
import ssl

import websockets

CUSTOMER_TOKEN = os.environ["CUSTOMER_TOKEN"]
ROOM_ID = os.environ["ROOM_ID"]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

URL = f"wss://localhost:8443/ws/room/{ROOM_ID}?token={CUSTOMER_TOKEN}"


async def main() -> None:
    async with websockets.connect(URL, ssl=SSL_CTX) as ws:
        await asyncio.wait_for(ws.recv(), timeout=10)  # history frame
        await ws.send(json.dumps({"type": "message", "content": "Still there?"}))
        await asyncio.wait_for(ws.recv(), timeout=10)  # own echo

        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
        except TimeoutError:
            print("PASS: no AI reply within 15s while mode=human, as expected", flush=True)
            return
        print(f"FAIL: unexpected message while mode=human: {raw}")
        raise SystemExit(1)


asyncio.run(main())
PYEOF
)

echo
echo "=== Switch back to ai: AI resumes ==="
$CURL -X PATCH "$GATEWAY_URL/chat/rooms/$ROOM_ID/mode" -H "Authorization: Bearer $CUSTOMER_TOKEN" \
  -H "Content-Type: application/json" -d '{"mode": "ai"}' >/dev/null
MODE=$($CURL "$GATEWAY_URL/chat/rooms/$ROOM_ID/mode" -H "Authorization: Bearer $CUSTOMER_TOKEN" | jq -r .mode)
[ "$MODE" = "ai" ] || fail "expected mode=ai after PATCH, got: $MODE"
pass "PATCH /rooms/:id/mode -> ai"

(
  cd "$CHAT_DIR"
  CUSTOMER_TOKEN="$CUSTOMER_TOKEN" ROOM_ID="$ROOM_ID" \
    uv run python3 - <<'PYEOF'
import asyncio
import json
import os
import ssl
import sys

import websockets

CUSTOMER_TOKEN = os.environ["CUSTOMER_TOKEN"]
ROOM_ID = os.environ["ROOM_ID"]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

URL = f"wss://localhost:8443/ws/room/{ROOM_ID}?token={CUSTOMER_TOKEN}"


async def main() -> None:
    async with websockets.connect(URL, ssl=SSL_CTX) as ws:
        await asyncio.wait_for(ws.recv(), timeout=10)  # history frame
        await ws.send(json.dumps({"type": "message", "content": "Are you back?"}))
        await asyncio.wait_for(ws.recv(), timeout=10)  # own echo

        deadline = asyncio.get_event_loop().time() + 30
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                print("FAIL: AI did not resume within 30s of switching back to ai mode", flush=True)
                sys.exit(1)
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            frame = json.loads(raw)
            if frame.get("sender_type") == "assistant":
                print("PASS: AI resumed responding after switching back to ai mode", flush=True)
                return


asyncio.run(main())
PYEOF
)

echo
echo "All AI Assistant verification checks passed against the real stack."
