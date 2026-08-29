#!/usr/bin/env bash
# End-to-end verification of chat-gate + internal-gate + chat-opa -- the
# sidecar chain that replaced chat's own internal-token verification
# (services/chat/src/chat/auth.py's now-removed verify_internal_token/
# require_admin/require_assistant/require_admin_or_assistant). See
# scripts/verify-orders-gate.sh for the same "route-level tier only,
# ownership stays inline" idea; chat is the same hybrid shape (room
# ownership is either a pure function of room_id + sub, or -- attachments
# -- needs a DB lookup this gate has no access to, so it stays in
# chat's own code either way).
#
# Also covers the /ws/room/{id} WebSocket handshake -- it's a plain HTTP
# GET with an Upgrade header, so auth_request gates it exactly like any
# REST call (see nginx/internal-gate/chat.conf's comment). This script
# only checks the handshake's HTTP status (401 vs 101/whatever chat
# itself returns) via curl's raw Upgrade headers, not a full WS session --
# services/chat/tests/test_websocket.py covers the app-level behavior.
#
# Bypasses nginx (the external Gateway) the same way
# scripts/verify-gateway.sh's DIRECT() does: a throwaway container on the
# compose network hitting chat:8000 directly, since chat publishes no
# host port.
#
# Requires: curl, openssl, docker compose. Run after `docker compose up -d
# --build chat chat-opa chat-verify chat-gate chat-db redis kafka
# object-storage object-storage-init`.
set -euo pipefail

NETWORK="internstore-migrate_default"
SECRET="dev-only-internal-secret-change-me"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

b64url() {
  openssl base64 -e -A | tr '+/' '-_' | tr -d '='
}

mint_token() {
  local sub="$1" role="$2" secret="$3" exp_offset="${4:-300}"
  local header='{"alg":"HS256","typ":"JWT"}'
  local now
  now=$(date +%s)
  local payload
  payload=$(printf '{"sub":"%s","role":"%s","iss":"internstore-gateway","iat":%d,"exp":%d}' "$sub" "$role" "$now" "$((now + exp_offset))")
  local signing_input
  signing_input="$(printf '%s' "$header" | b64url).$(printf '%s' "$payload" | b64url)"
  local sig
  sig=$(printf '%s' "$signing_input" | openssl dgst -sha256 -hmac "$secret" -binary | b64url)
  echo "$signing_input.$sig"
}

DIRECT() {
  docker run --rm --network "$NETWORK" curlimages/curl -s -o /dev/null -w "%{http_code}" "$@"
}

ADMIN_TOKEN=$(mint_token "admin-1" "admin" "$SECRET")
ASSISTANT_TOKEN=$(mint_token "ai-assistant" "assistant" "$SECRET")
CUSTOMER_TOKEN=$(mint_token "cust-1" "customer" "$SECRET")

echo "=== 1. /health is public (no token) ==="
STATUS=$(DIRECT http://chat:8000/health)
[ "$STATUS" = "200" ] || fail "GET /health with no token got $STATUS, expected 200"
pass "GET /health with no token -> 200"

echo "=== 2. GET /rooms is admin-only ==="
STATUS=$(DIRECT http://chat:8000/rooms)
[ "$STATUS" = "401" ] || fail "GET /rooms with no token got $STATUS, expected 401"
pass "GET /rooms with no token -> 401"

STATUS=$(DIRECT http://chat:8000/rooms -H "X-Internal-Token: $CUSTOMER_TOKEN")
[ "$STATUS" = "403" ] || fail "GET /rooms as customer got $STATUS, expected 403"
pass "GET /rooms as customer -> 403 (valid token, wrong role)"

STATUS=$(DIRECT http://chat:8000/rooms -H "X-Internal-Token: $ADMIN_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /rooms as admin got $STATUS, expected 200"
pass "GET /rooms as admin -> 200"

echo "=== 3. GET /rooms/{id}/messages is admin-or-assistant ==="
ROOM_ID="room_test-1"
STATUS=$(DIRECT "http://chat:8000/rooms/$ROOM_ID/messages" -H "X-Internal-Token: $CUSTOMER_TOKEN")
[ "$STATUS" = "403" ] || fail "GET /rooms/{id}/messages as customer got $STATUS, expected 403"
pass "GET /rooms/{id}/messages as customer -> 403"

STATUS=$(DIRECT "http://chat:8000/rooms/$ROOM_ID/messages" -H "X-Internal-Token: $ASSISTANT_TOKEN")
# 404 (unknown room) is the real business-logic response -- what matters
# is it's not 401/403, i.e. the gate let the assistant through.
[ "$STATUS" = "404" ] || fail "GET /rooms/{id}/messages as assistant got $STATUS, expected 404 (business-logic response, not a gate rejection)"
pass "GET /rooms/{id}/messages as assistant -> 404 (business-logic response, gate let it through)"

echo "=== 4. POST /rooms/{id}/messages (internal, AI Assistant) is assistant-only ==="
STATUS=$(DIRECT -X POST "http://chat:8000/rooms/$ROOM_ID/messages" -H "Content-Type: application/json" \
  -H "X-Internal-Token: $ADMIN_TOKEN" -d '{"content": "hi"}')
[ "$STATUS" = "403" ] || fail "POST /rooms/{id}/messages as admin got $STATUS, expected 403 (assistant-only, not admin-or-assistant)"
pass "POST /rooms/{id}/messages as admin -> 403 (assistant-only, admin doesn't count here)"

STATUS=$(DIRECT -X POST "http://chat:8000/rooms/$ROOM_ID/messages" -H "Content-Type: application/json" \
  -H "X-Internal-Token: $ASSISTANT_TOKEN" -d '{"content": "hi"}')
[ "$STATUS" = "404" ] || fail "POST /rooms/{id}/messages as assistant got $STATUS, expected 404 (business-logic response, not a gate rejection)"
pass "POST /rooms/{id}/messages as assistant -> 404 (business-logic response, gate let it through)"

echo "=== 5. GET/PATCH /rooms/{id}/mode is 'any authenticated caller' (ownership check stays inline) ==="
STATUS=$(DIRECT "http://chat:8000/rooms/$ROOM_ID/mode")
[ "$STATUS" = "401" ] || fail "GET /rooms/{id}/mode with no token got $STATUS, expected 401"
pass "GET /rooms/{id}/mode with no token -> 401"

STATUS=$(DIRECT "http://chat:8000/rooms/$ROOM_ID/mode" -H "X-Internal-Token: $CUSTOMER_TOKEN")
# The gate lets any authenticated caller through; chat's own
# _room_owner_matches then decides -- 403 here (not this customer's room)
# is the app's own ownership rule, not a gate rejection for role.
[ "$STATUS" = "403" ] || fail "GET /rooms/{id}/mode as unrelated customer got $STATUS, expected 403 (app-level ownership check, gate let it through)"
pass "GET /rooms/{id}/mode as unrelated customer -> 403 (app-level ownership check, not a gate rejection)"

echo "=== 6. WebSocket handshake (/ws/room/{id}) goes through the same gate ==="
WS_STATUS=$(docker run --rm --network "$NETWORK" curlimages/curl -s -o /dev/null -w "%{http_code}" \
  -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  "http://chat:8000/ws/room/$ROOM_ID")
[ "$WS_STATUS" = "401" ] || fail "WS handshake with no token got $WS_STATUS, expected 401"
pass "WS handshake with no token -> 401 (auth_request gates the handshake too)"

echo
echo "All chat-gate verification checks passed."
