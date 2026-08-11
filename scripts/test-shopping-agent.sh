#!/usr/bin/env bash
# End-to-end verification of the shopping agent (STR-146) against the real
# stack: real Keycloak login, real Chat websocket, real MCP Gateway, real
# Orders cart, a real OpenAI round-trip for both the chat reply and the
# search_products embedding (requires a working OPENAI_API_KEY on both
# ai-assistant and mcp-gateway — see services/ai-assistant/README.md's
# dev-gaps note).
#
# Covers the ticket's own script description:
#   1. Customer logs in, opens chat, asks "find me a Gouda cheese under
#      $20" -> the agent's reply references a real Catalog product match.
#   2. Customer asks "add it to my cart" -> GET /cart (a direct REST call,
#      NOT through the agent/chat) shows the item.
#   3. No order or payment was created anywhere in the process — cart-
#      building only, this ticket adds no checkout/payment tool.
#
# Requires: curl, jq, python3, docker compose, and services/chat's own
# uv-managed venv (reused for its `websockets` dependency, same as
# scripts/test-ai-assistant.sh). Run after `docker compose up -d --build`
# (needs chat, ai-assistant, ai-db, mcp-gateway, orders, catalog, kafka,
# kafka-topic-init, redis, nginx, keycloak, auth-backend all healthy, and a
# real OPENAI_API_KEY set for both ai-assistant and mcp-gateway).
set -euo pipefail

KC_URL="http://localhost:8081"
AUTH_BACKEND_URL="http://localhost:3000"
GATEWAY_URL="https://localhost:8443/api"
REALM="internstore"
CLIENT_ID="internstore-web"
CURL="curl -sk"
CHAT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/services/chat"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

login() {
  curl -sf -X POST "$KC_URL/realms/$REALM/protocol/openid-connect/token" \
    -d "client_id=$CLIENT_ID" -d "grant_type=password" \
    -d "username=$1" -d "password=$2" | jq -r .access_token
}

sub_of() {
  $CURL "$AUTH_BACKEND_URL/me" -H "Authorization: Bearer $1" | jq -r .sub
}

CUSTOMER_TOKEN=$(login "customer@example.com" "Customer123")
ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$CUSTOMER_TOKEN" != "null" ] || fail "customer login did not return an access token"
[ "$ADMIN_TOKEN" != "null" ] || fail "admin login did not return an access token"

CUSTOMER_SUB=$(sub_of "$CUSTOMER_TOKEN")
[ -n "$CUSTOMER_SUB" ] && [ "$CUSTOMER_SUB" != "null" ] || fail "could not resolve customer sub via /me"
ROOM_ID="room_${CUSTOMER_SUB}"

echo "=== Confirm no orders exist for this customer before we start ==="
BEFORE_ORDER_COUNT=$($CURL "$GATEWAY_URL/orders/orders" -H "Authorization: Bearer $CUSTOMER_TOKEN" | jq 'length')
pass "customer has $BEFORE_ORDER_COUNT order(s) on record before the run"

echo
echo "=== Seed a real, searchable Gouda product under \$20 ==="
CATEGORY_ID=$($CURL -X POST "$GATEWAY_URL/catalog/categories" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Dairy"}' | jq -r '.id // empty')
if [ -z "$CATEGORY_ID" ]; then
  # Category may already exist from a previous run — reuse it.
  CATEGORY_ID=$($CURL "$GATEWAY_URL/catalog/categories" -H "Authorization: Bearer $ADMIN_TOKEN" \
    | jq -r '.[] | select(.name == "Dairy") | .id' | head -n1)
fi
[ -n "$CATEGORY_ID" ] || fail "could not create or find a Dairy category"

PRODUCT_NAME="Gouda Cheese $$-$RANDOM"
PRODUCT_ID=$($CURL -X POST "$GATEWAY_URL/catalog/products" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\": \"$PRODUCT_NAME\", \"price\": 12.50, \"category_id\": \"$CATEGORY_ID\", \"description\": \"Aged Dutch Gouda\"}" \
  | jq -r '.id')
[ -n "$PRODUCT_ID" ] && [ "$PRODUCT_ID" != "null" ] || fail "could not create the Gouda product"

# POST /products doesn't stage ProductUpdated (only PATCH does — see
# scripts/seed-embeddings.sh's own note) — a no-op PATCH triggers the
# re-embed AI Assistant's catalog-events consumer needs before
# search_products can find this product.
$CURL -X PATCH "$GATEWAY_URL/catalog/products/$PRODUCT_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\": \"$PRODUCT_NAME\"}" >/dev/null
pass "created and staged embedding for product $PRODUCT_ID ($PRODUCT_NAME, \$12.50)"

echo
echo "=== Chat: ask for a Gouda under \$20, then ask to add it to the cart ==="
(
  cd "$CHAT_DIR"
  CUSTOMER_TOKEN="$CUSTOMER_TOKEN" ROOM_ID="$ROOM_ID" PRODUCT_NAME="$PRODUCT_NAME" \
    uv run python3 - <<'PYEOF'
import asyncio
import json
import os
import ssl
import sys

import websockets

CUSTOMER_TOKEN = os.environ["CUSTOMER_TOKEN"]
ROOM_ID = os.environ["ROOM_ID"]
PRODUCT_NAME = os.environ["PRODUCT_NAME"]

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

        await ws.send(json.dumps({"type": "message", "content": "find me a Gouda cheese under $20"}))
        await recv_until(ws, lambda f: f.get("content") == "find me a Gouda cheese under $20", 10, "own echo")
        print("PASS: customer asked for a Gouda cheese under $20", flush=True)

        # search_products embeds the query, the ReAct loop's own OpenAI
        # round-trip, and the assistant posting back over REST all add up —
        # a generous window, same order of magnitude as test-ai-assistant.sh.
        search_reply = await recv_until(ws, lambda f: f.get("sender_type") == "assistant", 45, "agent's search reply")
        content = (search_reply.get("content") or "")
        assert "gouda" in content.lower() or PRODUCT_NAME.lower() in content.lower(), (
            f"agent reply did not reference a real Catalog product match: {search_reply}"
        )
        print("PASS: agent replied referencing a real product match from Catalog", flush=True)

        await ws.send(json.dumps({"type": "message", "content": "add it to my cart"}))
        await recv_until(ws, lambda f: f.get("content") == "add it to my cart", 10, "own echo")

        add_reply = await recv_until(ws, lambda f: f.get("sender_type") == "assistant", 45, "agent's add-to-cart reply")
        print(f"PASS: agent replied to the add-to-cart request: {add_reply.get('content')!r}", flush=True)


asyncio.run(main())
PYEOF
)

echo
echo "=== Verify via a direct REST call (NOT through the agent) that the cart actually has the item ==="
CART=$($CURL "$GATEWAY_URL/orders/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN")
IN_CART=$(echo "$CART" | jq --arg pid "$PRODUCT_ID" '[.items[] | select(.product_id == $pid)] | length')
[ "$IN_CART" -ge 1 ] || fail "GET /cart does not show the product the agent was asked to add: $CART"
pass "GET /cart (direct REST call) confirms the product is in the customer's cart"

echo
echo "=== Confirm no order or payment was created anywhere in the process ==="
AFTER_ORDER_COUNT=$($CURL "$GATEWAY_URL/orders/orders" -H "Authorization: Bearer $CUSTOMER_TOKEN" | jq 'length')
[ "$AFTER_ORDER_COUNT" -eq "$BEFORE_ORDER_COUNT" ] || fail "order count changed ($BEFORE_ORDER_COUNT -> $AFTER_ORDER_COUNT) — the agent must never checkout"
pass "order count unchanged ($AFTER_ORDER_COUNT) — the agent built a cart, nothing more"

echo
echo "All shopping agent verification checks passed against the real stack."
