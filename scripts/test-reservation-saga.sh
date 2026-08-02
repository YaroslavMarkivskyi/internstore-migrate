#!/usr/bin/env bash
# End-to-end verification of the reservation saga (Orders outbox + Inventory
# idempotent consumer) through the real gateway, real Keycloak-issued
# tokens, and a real Kafka broker — no mocks anywhere in this script.
#
# Covers:
#   1. Happy path: checkout -> (real Kafka round-trip) -> pending ->
#      pay -> paid -> (real Kafka round-trip) -> Inventory quantity
#      reflects the final decrement.
#   2. Insufficient-stock-at-reservation-time -> rejected. Deliberately
#      exercises the documented check-availability/reserved_quantity gap
#      (see docs/EVENT_BROKER.md#known-accepted-gaps-dev-only-stage): two
#      orders for the same product both pass the optimistic pre-check
#      because it ignores reserved_quantity, but only the first actually
#      gets the stock — the second's real reservation fails.
#   3. Expired reservation -> cancelled, using the short dev-only TTL
#      (RESERVATION_TTL_SECONDS=30 / RESERVATION_CHECK_INTERVAL_SECONDS=5
#      in docker-compose.yml).
#
# Requires: curl, jq, python3, docker compose. Run after
# `docker compose up -d --build` (needs kafka, kafka-topic-init, orders,
# inventory, nginx, keycloak all healthy).
set -euo pipefail

KC_URL="http://localhost:8081"
GATEWAY_URL="https://localhost:8443/api/orders"
INVENTORY_URL="https://localhost:8443/api/inventory"
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

seed_stock() {
  # $1 = admin token, $2 = product_id, $3 = quantity
  local stock_id
  stock_id=$($CURL -X POST "$INVENTORY_URL/stocks" \
    -H "Authorization: Bearer $1" -H "Content-Type: application/json" \
    -d "{\"name\": \"Saga smoke stock $$-$RANDOM\"}" | jq -r .id)
  [ -n "$stock_id" ] && [ "$stock_id" != "null" ] || fail "seed_stock: could not create stock"
  $CURL -X POST "$INVENTORY_URL/stocks/$stock_id/items" \
    -H "Authorization: Bearer $1" -H "Content-Type: application/json" \
    -d "{\"product_id\": \"$2\", \"quantity\": $3}" >/dev/null
}

order_status() {
  # $1 = token, $2 = order_id
  $CURL "$GATEWAY_URL/orders/$2" -H "Authorization: Bearer $1" | jq -r .status
}

item_quantity() {
  # $1 = token, $2 = product_id
  $CURL "$INVENTORY_URL/items" -H "Authorization: Bearer $1" \
    | jq -r ".[] | select(.product_id==\"$2\") | .quantity"
}

# Polls $2() every 2s until it prints $3, or fails after $1 seconds.
poll_until() {
  local timeout_s="$1" check_cmd="$2" expected="$3" label="$4"
  local elapsed=0
  while [ "$elapsed" -lt "$timeout_s" ]; do
    local actual
    actual=$(eval "$check_cmd")
    if [ "$actual" = "$expected" ]; then
      pass "$label (took ~${elapsed}s)"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  fail "$label: timed out after ${timeout_s}s waiting for '$expected', last saw '$actual'"
}

CUSTOMER_TOKEN=$(login "customer@example.com" "Customer123")
ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$CUSTOMER_TOKEN" != "null" ] || fail "customer login did not return an access token"
[ "$ADMIN_TOKEN" != "null" ] || fail "admin login did not return an access token"

echo "=== 1. Happy path: checkout -> pending -> pay -> paid -> StockDecremented ==="
PRODUCT_A=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_A" 10

$CURL -X POST "$GATEWAY_URL/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_A\", \"quantity\": 3}" >/dev/null

CHECKOUT=$($CURL -X POST "$GATEWAY_URL/checkout" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d '{"contact_name": "Saga Customer", "contact_email": "customer@example.com", "payment_method": "card"}')
ORDER_A=$(echo "$CHECKOUT" | jq -r .id)
[ -n "$ORDER_A" ] && [ "$ORDER_A" != "null" ] || fail "checkout did not return an order id: $CHECKOUT"
[ "$(echo "$CHECKOUT" | jq -r .status)" = "new" ] || fail "expected status=new right after checkout, got: $CHECKOUT"
pass "checkout -> 201, order $ORDER_A created with status=new"

poll_until 30 "order_status '$CUSTOMER_TOKEN' '$ORDER_A'" "pending" \
  "OrderCreated -> (real Kafka) -> Inventory reserves -> StockReserved -> (real Kafka) -> status=pending"

PAY=$($CURL -X POST "$GATEWAY_URL/orders/$ORDER_A/pay" -H "Authorization: Bearer $CUSTOMER_TOKEN")
[ "$(echo "$PAY" | jq -r .status)" = "paid" ] || fail "expected status=paid after pay, got: $PAY"
pass "POST /orders/:id/pay -> paid"

poll_until 30 "item_quantity '$ADMIN_TOKEN' '$PRODUCT_A'" "7" \
  "PaymentConfirmed -> (real Kafka) -> Inventory decrements -> quantity 10 -> 7"

echo "=== 2. Reservation-time insufficient stock -> rejected upfront (STR-129: check-availability subtracts reserved_quantity) ==="
PRODUCT_B=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_B" 5

$CURL -X POST "$GATEWAY_URL/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_B\", \"quantity\": 5}" >/dev/null
ORDER_B1=$($CURL -X POST "$GATEWAY_URL/checkout" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d '{"contact_name": "Saga Customer", "contact_email": "customer@example.com", "payment_method": "card"}' | jq -r .id)
[ -n "$ORDER_B1" ] && [ "$ORDER_B1" != "null" ] || fail "first checkout for product B did not return an order id"
poll_until 30 "order_status '$CUSTOMER_TOKEN' '$ORDER_B1'" "pending" \
  "first order for product B reserves the full quantity (5) -> pending"

# STR-129 fixed check-availability to subtract reserved_quantity, so it now
# correctly sees 0 effectively-available stock (5 held by order B1's
# reservation) and Orders rejects the second checkout synchronously with
# 409, instead of accepting it and only failing later via the async
# reservation saga.
$CURL -X POST "$GATEWAY_URL/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_B\", \"quantity\": 5}" >/dev/null
CHECKOUT_B2_STATUS=$($CURL -o /dev/null -w "%{http_code}" -X POST "$GATEWAY_URL/checkout" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d '{"contact_name": "Saga Customer", "contact_email": "customer@example.com", "payment_method": "card"}')
[ "$CHECKOUT_B2_STATUS" = "409" ] || fail "second checkout for product B got $CHECKOUT_B2_STATUS, expected 409 (insufficient effective stock)"
pass "second checkout for product B rejected synchronously (409) -- check-availability correctly saw 0 effectively-available stock"

# A 409 leaves the cart untouched (checkout only clears the cart on
# success) -- remove product B so it doesn't also fail section 3's checkout
# for an unrelated product sharing the same customer's cart.
$CURL -X DELETE "$GATEWAY_URL/cart/items/$PRODUCT_B" -H "Authorization: Bearer $CUSTOMER_TOKEN" >/dev/null

echo "=== 3. Expired reservation -> cancelled (short dev-only TTL) ==="
PRODUCT_C=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_C" 5

$CURL -X POST "$GATEWAY_URL/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_C\", \"quantity\": 2}" >/dev/null
ORDER_C=$($CURL -X POST "$GATEWAY_URL/checkout" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d '{"contact_name": "Saga Customer", "contact_email": "customer@example.com", "payment_method": "card"}' | jq -r .id)
[ -n "$ORDER_C" ] && [ "$ORDER_C" != "null" ] || fail "checkout for product C did not return an order id"
poll_until 30 "order_status '$CUSTOMER_TOKEN' '$ORDER_C'" "pending" "order C reserved -> pending"

# Deliberately never paid. RESERVATION_TTL_SECONDS=30 / CHECK_INTERVAL=5 in
# docker-compose.yml -> should expire well within this timeout.
poll_until 60 "order_status '$CUSTOMER_TOKEN' '$ORDER_C'" "cancelled" \
  "reservation TTL expires -> ReservationExpired -> (real Kafka) -> status=cancelled"

poll_until 15 "item_quantity '$ADMIN_TOKEN' '$PRODUCT_C'" "5" \
  "expiry released reserved_quantity -> quantity back to 5 (never actually decremented)"

echo
echo "All reservation-saga verification checks passed against the real Kafka broker."
