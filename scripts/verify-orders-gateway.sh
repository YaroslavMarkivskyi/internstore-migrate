#!/usr/bin/env bash
# End-to-end verification of the Orders service through the real gateway
# (nginx + auth-backend), against the real Inventory service (not mocked),
# with real Firebase-issued tokens for the registered-customer flow and the
# guest-cookie fallback minted by auth-backend for the unauthenticated flow.
# Covers:
#
#   1. Registered-customer cart -> checkout happy path (real Inventory stock)
#   2. Registered-customer checkout with insufficient stock (real Inventory,
#      not mocked) -> 409, no Order created
#   3. Guest flow: no Authorization header, guest cookie issued and reused,
#      cart -> checkout happy path, insufficient-stock checkout
#   4. Guest-allowlist boundary: guests can check out but cannot list order
#      history (/api/orders/orders requires a real Firebase login)
#   5. /api/orders/orders with neither Bearer token nor guest cookie -> 401
#
# Requires: curl, jq, python3, docker compose. Run after
# `docker compose up -d --build inventory-db inventory orders-db orders nginx`.
set -euo pipefail

FIREBASE_AUTH_EMULATOR_URL="http://localhost:9099"
GATEWAY_URL="https://localhost:8443/api/orders"
INVENTORY_URL="https://localhost:8443/api/inventory"
FIREBASE_PROJECT_ID="internstore-dev"
CURL="curl -sk"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

login() {
  curl -sf -X POST "$FIREBASE_AUTH_EMULATOR_URL/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$1\",\"password\":\"$2\",\"returnSecureToken\":true}" | jq -r .idToken
}

seed_stock() {
  # $1 = admin token, $2 = product_id, $3 = quantity
  local stock_id
  stock_id=$($CURL -X POST "$INVENTORY_URL/stocks" \
    -H "Authorization: Bearer $1" -H "Content-Type: application/json" \
    -d "{\"name\": \"Orders smoke stock $$-$RANDOM\"}" | jq -r .id)
  [ -n "$stock_id" ] && [ "$stock_id" != "null" ] || fail "seed_stock: could not create stock"
  $CURL -X POST "$INVENTORY_URL/stocks/$stock_id/items" \
    -H "Authorization: Bearer $1" -H "Content-Type: application/json" \
    -d "{\"product_id\": \"$2\", \"quantity\": $3}" >/dev/null
}

CUSTOMER_TOKEN=$(login "customer@example.com" "Customer123")
ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$CUSTOMER_TOKEN" != "null" ] || fail "customer login did not return an access token"
[ "$ADMIN_TOKEN" != "null" ] || fail "admin login did not return an access token"

echo "=== 1. Registered-customer cart -> checkout happy path ==="
PRODUCT_A=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_A" 10

ADD=$($CURL -X POST "$GATEWAY_URL/cart" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_A\", \"quantity\": 3}")
[ "$(echo "$ADD" | jq -r '.items[0].quantity')" = "3" ] || fail "add to cart failed: $ADD"
pass "customer cart add -> quantity 3"

CHECKOUT=$($CURL -X POST "$GATEWAY_URL/checkout" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d '{"contact_name": "Real Customer", "contact_email": "customer@example.com", "payment_method": "card"}')
ORDER_ID=$(echo "$CHECKOUT" | jq -r .id)
[ -n "$ORDER_ID" ] && [ "$ORDER_ID" != "null" ] || fail "checkout did not return an order id: $CHECKOUT"
[ "$(echo "$CHECKOUT" | jq -r .status)" = "new" ] || fail "expected status=new, got: $CHECKOUT"
pass "customer checkout -> 201, order $ORDER_ID created"

CART_AFTER=$($CURL "$GATEWAY_URL/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN")
[ "$(echo "$CART_AFTER" | jq -c .items)" = "[]" ] || fail "cart was not cleared after checkout: $CART_AFTER"
pass "cart cleared after checkout"

LIST=$($CURL "$GATEWAY_URL/orders" -H "Authorization: Bearer $CUSTOMER_TOKEN")
echo "$LIST" | jq -e ".[] | select(.id==\"$ORDER_ID\")" >/dev/null || fail "GET /orders did not include the new order: $LIST"
pass "GET /orders lists the new order"

DETAIL=$($CURL "$GATEWAY_URL/orders/$ORDER_ID" -H "Authorization: Bearer $CUSTOMER_TOKEN")
[ "$(echo "$DETAIL" | jq -r .id)" = "$ORDER_ID" ] || fail "GET /orders/:id mismatch: $DETAIL"
pass "GET /orders/:id matches"

echo "=== 2. Registered-customer checkout with insufficient stock (real Inventory) ==="
PRODUCT_B=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_B" 2

$CURL -X POST "$GATEWAY_URL/cart" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_B\", \"quantity\": 50}" >/dev/null

ORDERS_BEFORE=$($CURL "$GATEWAY_URL/orders" -H "Authorization: Bearer $CUSTOMER_TOKEN" | jq 'length')

STATUS=$($CURL -o /tmp/orders-checkout-409.json -w "%{http_code}" -X POST "$GATEWAY_URL/checkout" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d '{"contact_name": "Real Customer", "contact_email": "customer@example.com", "payment_method": "card"}')
[ "$STATUS" = "409" ] || fail "expected 409 for insufficient stock, got $STATUS: $(cat /tmp/orders-checkout-409.json)"
AVAILABLE=$(jq -r '.items[0].available' /tmp/orders-checkout-409.json)
[ "$AVAILABLE" = "2" ] || fail "expected available=2 in 409 breakdown, got: $(cat /tmp/orders-checkout-409.json)"
pass "checkout with insufficient real Inventory stock -> 409 with matching breakdown"

ORDERS_AFTER=$($CURL "$GATEWAY_URL/orders" -H "Authorization: Bearer $CUSTOMER_TOKEN" | jq 'length')
[ "$ORDERS_AFTER" = "$ORDERS_BEFORE" ] || fail "order count changed after a failed checkout ($ORDERS_BEFORE -> $ORDERS_AFTER)"
pass "no Order created on insufficient-stock checkout"

# clean up the leftover cart item so it doesn't affect later runs
$CURL -X DELETE "$GATEWAY_URL/cart/items/$PRODUCT_B" -H "Authorization: Bearer $CUSTOMER_TOKEN" >/dev/null

echo "=== 3. Guest flow: cookie issuance, reuse, checkout ==="
GUEST_JAR=$(mktemp)
trap 'rm -f "$GUEST_JAR" /tmp/orders-checkout-409.json' EXIT

PRODUCT_C=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_C" 5

GUEST_ADD_1_HEADERS=$($CURL -D - -o /tmp/orders-guest-add1.json -c "$GUEST_JAR" -X POST "$GATEWAY_URL/cart" \
  -H "Content-Type: application/json" -d "{\"product_id\": \"$PRODUCT_C\", \"quantity\": 1}")
echo "$GUEST_ADD_1_HEADERS" | grep -qi '^HTTP/.* 201' || fail "guest cart add (no auth) did not return 201: $GUEST_ADD_1_HEADERS"
echo "$GUEST_ADD_1_HEADERS" | grep -qi '^set-cookie: is_guest_id=' || fail "guest cart add did not set is_guest_id cookie"
pass "unauthenticated cart add -> 201 + guest cookie issued"

PRODUCT_D=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_D" 5
$CURL -b "$GUEST_JAR" -X POST "$GATEWAY_URL/cart" \
  -H "Content-Type: application/json" -d "{\"product_id\": \"$PRODUCT_D\", \"quantity\": 1}" >/dev/null

GUEST_CART=$($CURL -b "$GUEST_JAR" "$GATEWAY_URL/cart")
GUEST_ITEM_COUNT=$(echo "$GUEST_CART" | jq '.items | length')
[ "$GUEST_ITEM_COUNT" = "2" ] || fail "expected the same guest identity to accumulate 2 cart items, got: $GUEST_CART"
pass "guest identity reused via cookie across requests (2 items in one cart)"

GUEST_CHECKOUT=$($CURL -b "$GUEST_JAR" -X POST "$GATEWAY_URL/checkout" \
  -H "Content-Type: application/json" \
  -d '{"contact_name": "Guest Buyer", "contact_email": "guest@example.com", "payment_method": "card"}')
GUEST_ORDER_ID=$(echo "$GUEST_CHECKOUT" | jq -r .id)
[ -n "$GUEST_ORDER_ID" ] && [ "$GUEST_ORDER_ID" != "null" ] || fail "guest checkout did not return an order id: $GUEST_CHECKOUT"
pass "guest checkout (cookie only, no Bearer token) -> 201"

echo "=== 4. Guest insufficient-stock checkout (real Inventory) ==="
PRODUCT_E=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_E" 1
$CURL -b "$GUEST_JAR" -X POST "$GATEWAY_URL/cart" \
  -H "Content-Type: application/json" -d "{\"product_id\": \"$PRODUCT_E\", \"quantity\": 99}" >/dev/null

STATUS=$($CURL -b "$GUEST_JAR" -o /tmp/orders-guest-409.json -w "%{http_code}" -X POST "$GATEWAY_URL/checkout" \
  -H "Content-Type: application/json" \
  -d '{"contact_name": "Guest Buyer", "contact_email": "guest@example.com", "payment_method": "card"}')
[ "$STATUS" = "409" ] || fail "expected 409 for guest insufficient-stock checkout, got $STATUS"
pass "guest insufficient-stock checkout -> 409 (real Inventory)"
rm -f /tmp/orders-guest-409.json /tmp/orders-guest-add1.json

echo "=== 5. Guest-allowlist boundary: guests cannot list order history ==="
STATUS=$($CURL -b "$GUEST_JAR" -o /dev/null -w "%{http_code}" "$GATEWAY_URL/orders")
[ "$STATUS" = "401" ] || fail "expected 401 for guest GET /orders (outside the allowlist), got $STATUS"
pass "GET /orders with only a guest cookie -> 401 (guest can check out but not list orders)"

echo "=== 6. /api/orders/orders with no credentials at all -> 401 ==="
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/orders")
[ "$STATUS" = "401" ] || fail "expected 401 for GET /orders with no token/cookie, got $STATUS"
pass "GET /orders with no credentials -> 401"

echo
echo "All Orders gateway verification checks passed (including guest checkout)."
