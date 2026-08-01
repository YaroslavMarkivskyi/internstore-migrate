#!/usr/bin/env bash
# End-to-end verification of the Inventory service through the real gateway
# (nginx + auth-backend), with real Keycloak-issued tokens — not the
# in-process JWTs the pytest suite mints. Covers:
#
#   1. No token -> 401 on /api/inventory/*
#   2. POST /stocks: customer -> 403, admin -> 201 (STR-118 pattern)
#   3. Read endpoints (GET /stocks, /stocks/:id/items, /items) reachable with
#      a valid customer token
#   4. POST /stocks/:id/items (receive stock): customer -> 403, admin -> 201,
#      quantity accumulates on repeat calls
#   5. POST /stocks/:id/items/:itemId/move: customer -> 403, admin -> 200,
#      quantity actually moves between stocks
#   6. POST /stocks/check-availability: sufficient / insufficient / partial
#
# Requires: curl, jq, docker compose. Run after `docker compose up -d`.
set -euo pipefail

KC_URL="http://localhost:8081"
GATEWAY_URL="https://localhost:8443/api/inventory"
REALM="internstore"
CLIENT_ID="internstore-web"
CURL="curl -sk"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

login() {
  curl -sf -X POST "$KC_URL/realms/$REALM/protocol/openid-connect/token" \
    -d "client_id=$CLIENT_ID" -d "grant_type=password" \
    -d "username=$1" -d "password=$2" | jq -r .access_token
}

CUSTOMER_TOKEN=$(login "customer@example.com" "Customer123")
ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$CUSTOMER_TOKEN" != "null" ] || fail "customer login did not return an access token"
[ "$ADMIN_TOKEN" != "null" ] || fail "admin login did not return an access token"

echo "=== 1. No token -> 401 ==="
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/stocks")
[ "$STATUS" = "401" ] || fail "GET /stocks with no token got $STATUS, expected 401"
pass "GET /stocks with no token -> 401"

echo "=== 2. POST /stocks: customer 403, admin 201 ==="
STOCK_A_NAME="Smoke Warehouse A $$"
STATUS=$($CURL -o /dev/null -w "%{http_code}" -X POST "$GATEWAY_URL/stocks" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\": \"$STOCK_A_NAME\"}")
[ "$STATUS" = "403" ] || fail "POST /stocks as customer got $STATUS, expected 403"
pass "POST /stocks as customer -> 403"

STOCK_A=$($CURL -X POST "$GATEWAY_URL/stocks" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\": \"$STOCK_A_NAME\"}")
STOCK_A_ID=$(echo "$STOCK_A" | jq -r .id)
[ "$STOCK_A_ID" != "null" ] && [ -n "$STOCK_A_ID" ] || fail "POST /stocks as admin did not return an id (got: $STOCK_A)"
pass "POST /stocks as admin -> 201 ($STOCK_A_ID)"

STOCK_B_NAME="Smoke Warehouse B $$"
STOCK_B=$($CURL -X POST "$GATEWAY_URL/stocks" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\": \"$STOCK_B_NAME\"}")
STOCK_B_ID=$(echo "$STOCK_B" | jq -r .id)
[ "$STOCK_B_ID" != "null" ] && [ -n "$STOCK_B_ID" ] || fail "second POST /stocks as admin did not return an id (got: $STOCK_B)"
pass "second stock created for the move test ($STOCK_B_ID)"

echo "=== 3. Read endpoints reachable with a customer token ==="
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/stocks" -H "Authorization: Bearer $CUSTOMER_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /stocks as customer got $STATUS, expected 200"
pass "GET /stocks as customer -> 200"

STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/stocks/$STOCK_A_ID/items" -H "Authorization: Bearer $CUSTOMER_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /stocks/:id/items as customer got $STATUS, expected 200"
pass "GET /stocks/:id/items as customer -> 200"

STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/items" -H "Authorization: Bearer $CUSTOMER_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /items as customer got $STATUS, expected 200"
pass "GET /items as customer -> 200"

echo "=== 4. POST /stocks/:id/items (receive): customer 403, admin 201, accumulates ==="
PRODUCT_ID=$(python3 -c "import uuid; print(uuid.uuid4())")

STATUS=$($CURL -o /dev/null -w "%{http_code}" -X POST "$GATEWAY_URL/stocks/$STOCK_A_ID/items" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 5}")
[ "$STATUS" = "403" ] || fail "POST /stocks/:id/items as customer got $STATUS, expected 403"
pass "POST /stocks/:id/items as customer -> 403"

RECEIVE_1=$($CURL -X POST "$GATEWAY_URL/stocks/$STOCK_A_ID/items" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 5}")
QTY_1=$(echo "$RECEIVE_1" | jq -r .quantity)
ITEM_ID=$(echo "$RECEIVE_1" | jq -r .id)
[ "$QTY_1" = "5" ] || fail "first receive expected quantity 5, got: $RECEIVE_1"
pass "POST /stocks/:id/items as admin -> 201, quantity=5 ($ITEM_ID)"

RECEIVE_2=$($CURL -X POST "$GATEWAY_URL/stocks/$STOCK_A_ID/items" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 3}")
QTY_2=$(echo "$RECEIVE_2" | jq -r .quantity)
[ "$QTY_2" = "8" ] || fail "second receive expected accumulated quantity 8, got: $RECEIVE_2"
pass "repeat POST /stocks/:id/items accumulates quantity (5 + 3 = 8)"

echo "=== 5. POST /stocks/:id/items/:itemId/move: customer 403, admin 200, quantity moves ==="
STATUS=$($CURL -o /dev/null -w "%{http_code}" -X POST "$GATEWAY_URL/stocks/$STOCK_A_ID/items/$ITEM_ID/move" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"to_stock_id\": \"$STOCK_B_ID\", \"quantity\": 2}")
[ "$STATUS" = "403" ] || fail "move as customer got $STATUS, expected 403"
pass "POST .../move as customer -> 403"

MOVE=$($CURL -X POST "$GATEWAY_URL/stocks/$STOCK_A_ID/items/$ITEM_ID/move" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"to_stock_id\": \"$STOCK_B_ID\", \"quantity\": 2}")
MOVE_STOCK=$(echo "$MOVE" | jq -r .stock_id)
MOVE_QTY=$(echo "$MOVE" | jq -r .quantity)
[ "$MOVE_STOCK" = "$STOCK_B_ID" ] && [ "$MOVE_QTY" = "2" ] || fail "move response unexpected: $MOVE"
pass "POST .../move as admin -> 200, 2 units landed on stock B"

SRC_ITEMS=$($CURL "$GATEWAY_URL/stocks/$STOCK_A_ID/items" -H "Authorization: Bearer $CUSTOMER_TOKEN")
SRC_QTY=$(echo "$SRC_ITEMS" | jq -r ".[] | select(.product_id==\"$PRODUCT_ID\") | .quantity")
[ "$SRC_QTY" = "6" ] || fail "source stock expected quantity 8 - 2 = 6, got: $SRC_ITEMS"
pass "source stock quantity decremented correctly (8 - 2 = 6)"

echo "=== 6. POST /stocks/check-availability: sufficient / insufficient / partial ==="
UNKNOWN_PRODUCT=$(python3 -c "import uuid; print(uuid.uuid4())")

SUFFICIENT=$($CURL -X POST "$GATEWAY_URL/stocks/check-availability" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"items\": [{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 8}]}")
[ "$(echo "$SUFFICIENT" | jq -r .sufficient)" = "true" ] || fail "expected sufficient=true, got: $SUFFICIENT"
pass "check-availability: 8 requested of 8 available -> sufficient"

INSUFFICIENT=$($CURL -X POST "$GATEWAY_URL/stocks/check-availability" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"items\": [{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 100}]}")
[ "$(echo "$INSUFFICIENT" | jq -r .sufficient)" = "false" ] || fail "expected sufficient=false, got: $INSUFFICIENT"
pass "check-availability: 100 requested of 8 available -> insufficient"

PARTIAL=$($CURL -X POST "$GATEWAY_URL/stocks/check-availability" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"items\": [{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 1}, {\"product_id\": \"$UNKNOWN_PRODUCT\", \"quantity\": 1}]}")
[ "$(echo "$PARTIAL" | jq -r .sufficient)" = "false" ] || fail "expected top-level sufficient=false for partial mix, got: $PARTIAL"
KNOWN_OK=$(echo "$PARTIAL" | jq -r ".items[] | select(.product_id==\"$PRODUCT_ID\") | .sufficient")
UNKNOWN_OK=$(echo "$PARTIAL" | jq -r ".items[] | select(.product_id==\"$UNKNOWN_PRODUCT\") | .sufficient")
UNKNOWN_AVAILABLE=$(echo "$PARTIAL" | jq -r ".items[] | select(.product_id==\"$UNKNOWN_PRODUCT\") | .available")
[ "$KNOWN_OK" = "true" ] || fail "known product should be sufficient in partial mix, got: $PARTIAL"
[ "$UNKNOWN_OK" = "false" ] && [ "$UNKNOWN_AVAILABLE" = "0" ] || fail "unknown product should be 0 available / insufficient, got: $PARTIAL"
pass "check-availability: mixed request -> top-level false, per-item breakdown correct, unknown product treated as 0 stock"

echo
echo "All inventory gateway verification checks passed."
