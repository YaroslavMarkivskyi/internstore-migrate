#!/usr/bin/env bash
# End-to-end verification that a real checkout -> pay through Orders
# produces a real email in Mailpit via Notifications' Kafka consumer — not
# mocked anywhere: real Keycloak tokens, real gateway, real Kafka broker,
# real SMTP hop into Mailpit.
#
# Requires: curl, jq, python3, docker compose. Run after
# `docker compose up -d --build` (needs kafka, kafka-topic-init, mailpit,
# notifications, orders, inventory, nginx, keycloak all healthy).
set -euo pipefail

KC_URL="http://localhost:8081"
GATEWAY_URL="https://localhost:8443/api/orders"
INVENTORY_URL="https://localhost:8443/api/inventory"
MAILPIT_URL="http://localhost:8025"
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
    -d "{\"name\": \"Notifications smoke stock $$-$RANDOM\"}" | jq -r .id)
  [ -n "$stock_id" ] && [ "$stock_id" != "null" ] || fail "seed_stock: could not create stock"
  $CURL -X POST "$INVENTORY_URL/stocks/$stock_id/items" \
    -H "Authorization: Bearer $1" -H "Content-Type: application/json" \
    -d "{\"product_id\": \"$2\", \"quantity\": $3}" >/dev/null
}

order_status() {
  # $1 = token, $2 = order_id
  $CURL "$GATEWAY_URL/orders/$2" -H "Authorization: Bearer $1" | jq -r .status
}

# Searches Mailpit for a message to $1 whose subject contains $2, prints
# its message ID (empty if none found yet).
find_message_id() {
  curl -sf "$MAILPIT_URL/api/v1/search?query=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote('to:' + sys.argv[1]))" "$1")" \
    | jq -r --arg subject "$2" '.messages[] | select(.Subject | contains($subject)) | .ID' | head -n1
}

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

echo "=== Real checkout -> pay -> PaymentConfirmed email in Mailpit ==="
PRODUCT_A=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_A" 10

$CURL -X POST "$GATEWAY_URL/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_A\", \"quantity\": 2}" >/dev/null

CUSTOMER_EMAIL="customer@example.com"
CHECKOUT=$($CURL -X POST "$GATEWAY_URL/checkout" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"contact_name\": \"Notifications Customer\", \"contact_email\": \"$CUSTOMER_EMAIL\", \"payment_method\": \"card\"}")
ORDER_ID=$(echo "$CHECKOUT" | jq -r .id)
[ -n "$ORDER_ID" ] && [ "$ORDER_ID" != "null" ] || fail "checkout did not return an order id: $CHECKOUT"
pass "checkout -> 201, order $ORDER_ID created"

poll_until 30 "order_status '$CUSTOMER_TOKEN' '$ORDER_ID'" "pending" "order reserved -> pending"

PAY=$($CURL -X POST "$GATEWAY_URL/orders/$ORDER_ID/pay" -H "Authorization: Bearer $CUSTOMER_TOKEN")
[ "$(echo "$PAY" | jq -r .status)" = "paid" ] || fail "expected status=paid after pay, got: $PAY"
pass "POST /orders/:id/pay -> paid (publishes PaymentConfirmed)"

MESSAGE_ID=""
ELAPSED=0
while [ "$ELAPSED" -lt 30 ]; do
  MESSAGE_ID=$(find_message_id "$CUSTOMER_EMAIL" "$ORDER_ID")
  [ -n "$MESSAGE_ID" ] && break
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done
[ -n "$MESSAGE_ID" ] || fail "no email to $CUSTOMER_EMAIL mentioning order $ORDER_ID appeared in Mailpit within 30s"
pass "PaymentConfirmed -> (real Kafka) -> Notifications -> (real SMTP) -> email visible in Mailpit (took ~${ELAPSED}s)"

MESSAGE=$(curl -sf "$MAILPIT_URL/api/v1/message/$MESSAGE_ID")
echo "$MESSAGE" | jq -e ".To[0].Address == \"$CUSTOMER_EMAIL\"" >/dev/null || fail "email recipient mismatch: $MESSAGE"
echo "$MESSAGE" | jq -r .Subject | grep -qF "$ORDER_ID" || fail "email subject did not mention order id: $(echo "$MESSAGE" | jq -r .Subject)"
echo "$MESSAGE" | jq -r .Text | grep -qi "payment" || fail "email body did not mention payment: $(echo "$MESSAGE" | jq -r .Text)"
pass "email content verified via Mailpit REST API: correct recipient, subject, and body"

echo
echo "All notifications verification checks passed against the real Kafka broker and Mailpit."
