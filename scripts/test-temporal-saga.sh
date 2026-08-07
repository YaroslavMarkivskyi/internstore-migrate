#!/usr/bin/env bash
# End-to-end verification of the Temporal-orchestrated checkout
# (STR-139) through the real gateway, real Keycloak-issued tokens, a real
# Temporal server, and a real Kafka broker (for the escalation/fan-out
# side) — no mocks anywhere in this script. Parallel to, and does not
# replace, scripts/test-reservation-saga.sh (the existing Kafka-
# choreographed saga's own smoke test).
#
# Covers:
#   1. Happy path: POST /checkout/v2 -> CheckoutWorkflow runs reserve_stock
#      -> create_order -> charge_payment -> update_order_status(paid) ->
#      publish_order_confirmed -> order status Paid.
#   2. Payment failure (amount configured to fail Payments' dev-only
#      simulation, see services/payments/README.md's Failure simulation)
#      -> compensation fires (release_stock, mark_order_rejected) -> order
#      status Rejected, and Inventory's held stock is released.
#   3. Uses the Temporal CLI (via temporalio/admin-tools, since this
#      script runs on the host, not inside the compose network) to query
#      workflow history and assert the expected activity sequence appears.
#
# Requires: curl, jq, python3, docker compose, and network access to pull
# temporalio/admin-tools (for step 3's history query) if not already
# cached locally. Run after:
#   docker compose up -d --build \
#     temporal temporal-db temporal-ui payments payments-db \
#     checkout-workflow-worker orders inventory nginx keycloak kafka kafka-topic-init
set -euo pipefail

KC_URL="http://localhost:8081"
GATEWAY_URL="https://localhost:8443/api/orders"
INVENTORY_URL="https://localhost:8443/api/inventory"
REALM="internstore"
CLIENT_ID="internstore-web"
CURL="curl -sk"
COMPOSE_NETWORK="internstore-migrate_default"
ADMIN_TOOLS_IMAGE="temporalio/admin-tools:1.27.2-tctl-1.18.2-cli-1.1.1"

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
    -d "{\"name\": \"Temporal saga smoke stock $$-$RANDOM\"}" | jq -r .id)
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
  local actual=""
  while [ "$elapsed" -lt "$timeout_s" ]; do
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

# Queries Temporal's workflow history via a throwaway admin-tools
# container on the compose network (this script itself runs on the host,
# outside that network) and asserts every name in $2 (space-separated)
# appears somewhere in the history — a cheap but real check that the
# expected activities actually ran, not just that the workflow finished.
assert_workflow_history_contains() {
  local workflow_id="$1" expected_names="$2"
  local history
  history=$(docker run --rm --network "$COMPOSE_NETWORK" "$ADMIN_TOOLS_IMAGE" \
    temporal workflow show --address temporal:7233 --workflow-id "$workflow_id" 2>&1) \
    || fail "temporal workflow show failed for $workflow_id: $history"

  for name in $expected_names; do
    echo "$history" | grep -q "$name" || fail "workflow history for $workflow_id missing expected activity/event: $name"
  done
  pass "workflow $workflow_id history contains: $expected_names"
}

CUSTOMER_TOKEN=$(login "customer@example.com" "Customer123")
ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$CUSTOMER_TOKEN" != "null" ] || fail "customer login did not return an access token"
[ "$ADMIN_TOKEN" != "null" ] || fail "admin login did not return an access token"

echo "=== 1. Happy path: /checkout/v2 -> reserve -> order -> charge -> paid ==="
PRODUCT_A=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_A" 10

$CURL -X POST "$GATEWAY_URL/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_A\", \"quantity\": 3}" >/dev/null

CHECKOUT=$($CURL -X POST "$GATEWAY_URL/checkout/v2" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d '{"contact_name": "Temporal Customer", "contact_email": "customer@example.com", "payment_method": "card"}')
WORKFLOW_ID_A=$(echo "$CHECKOUT" | jq -r .workflow_id)
[ -n "$WORKFLOW_ID_A" ] && [ "$WORKFLOW_ID_A" != "null" ] || fail "checkout/v2 did not return a workflow_id: $CHECKOUT"
STATUS_A=$(echo "$CHECKOUT" | jq -r .status)
if [ "$STATUS_A" = "running" ]; then
  pass "checkout/v2 -> 202, workflow $WORKFLOW_ID_A still running past the wait window, polling"
else
  pass "checkout/v2 -> workflow $WORKFLOW_ID_A finished inline with status=$STATUS_A"
fi

ORDER_A=""
poll_until 30 "$CURL '$GATEWAY_URL/checkout/v2/$WORKFLOW_ID_A' -H 'Authorization: Bearer $CUSTOMER_TOKEN' | jq -r .status" "confirmed" \
  "CheckoutWorkflow $WORKFLOW_ID_A completes with status=confirmed"
ORDER_A=$($CURL "$GATEWAY_URL/checkout/v2/$WORKFLOW_ID_A" -H "Authorization: Bearer $CUSTOMER_TOKEN" | jq -r .order.id)
[ -n "$ORDER_A" ] && [ "$ORDER_A" != "null" ] || fail "confirmed workflow result had no order id"

poll_until 15 "order_status '$CUSTOMER_TOKEN' '$ORDER_A'" "paid" \
  "order $ORDER_A reflects the workflow's update_order_status(paid) activity"

assert_workflow_history_contains "$WORKFLOW_ID_A" "reserve_stock create_order charge_payment update_order_status publish_order_confirmed"

echo "=== 2. Payment failure -> compensation -> stock released, order Rejected ==="
PRODUCT_B=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_B" 5

$CURL -X POST "$GATEWAY_URL/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_B\", \"quantity\": 2}" >/dev/null

# Payments' dev-only failure simulation fails any charge whose amount ends
# in PAYMENT_FAIL_ON_AMOUNT_SUFFIX (default "99", see
# services/payments/README.md) — Catalog seeds product prices, not this
# script, so this assumes the demo catalog has at least one product priced
# to land on a ".99" total for quantity 2. If your local Catalog seed data
# doesn't produce one, adjust PRODUCT_B's price in Catalog first.
CHECKOUT_B=$($CURL -X POST "$GATEWAY_URL/checkout/v2" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d '{"contact_name": "Temporal Customer", "contact_email": "customer@example.com", "payment_method": "card"}')
WORKFLOW_ID_B=$(echo "$CHECKOUT_B" | jq -r .workflow_id)
[ -n "$WORKFLOW_ID_B" ] && [ "$WORKFLOW_ID_B" != "null" ] || fail "checkout/v2 did not return a workflow_id: $CHECKOUT_B"

poll_until 30 "$CURL '$GATEWAY_URL/checkout/v2/$WORKFLOW_ID_B' -H 'Authorization: Bearer $CUSTOMER_TOKEN' | jq -r .status" "rejected" \
  "CheckoutWorkflow $WORKFLOW_ID_B completes with status=rejected after payment failure"
ORDER_B=$($CURL "$GATEWAY_URL/checkout/v2/$WORKFLOW_ID_B" -H "Authorization: Bearer $CUSTOMER_TOKEN" | jq -r .order.id)
[ -n "$ORDER_B" ] && [ "$ORDER_B" != "null" ] || fail "rejected workflow result had no order id"

poll_until 15 "order_status '$CUSTOMER_TOKEN' '$ORDER_B'" "rejected" \
  "order $ORDER_B reflects the workflow's mark_order_rejected compensation activity"
poll_until 15 "item_quantity '$ADMIN_TOKEN' '$PRODUCT_B'" "5" \
  "release_stock compensation freed the held quantity -> back to 5"

assert_workflow_history_contains "$WORKFLOW_ID_B" "reserve_stock create_order charge_payment release_stock mark_order_rejected"

echo
echo "All Temporal-orchestrated checkout verification checks passed against a real Temporal server."
