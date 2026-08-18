#!/usr/bin/env bash
# K8s counterpart: scripts/k8s/test-temporal-saga.sh (STR-145). If you fix
# a bug in this script, check whether the same bug exists there too -- see
# STR-151, which found fixes made in one copy that were never ported to
# the other.
#
# End-to-end verification of the Temporal-orchestrated checkout
# (STR-139) through the real gateway, real Firebase-issued tokens, a real
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
#   3. Uses the `temporal` CLI already bundled in the `temporal` service
#      container (via `docker compose exec`, since this script itself
#      runs on the host, not inside the compose network) to query workflow
#      history and assert the expected activity sequence appears.
#
# Requires: curl, jq, python3, docker compose. Run after:
#   docker compose up -d --build \
#     temporal temporal-db temporal-ui payments payments-db \
#     checkout-workflow-worker orders inventory nginx firebase-emulator kafka kafka-topic-init
set -euo pipefail

FIREBASE_AUTH_EMULATOR_URL="http://localhost:9099"
GATEWAY_URL="https://localhost:8443/api/orders"
INVENTORY_URL="https://localhost:8443/api/inventory"
CATALOG_URL="https://localhost:8443/api/catalog"
FIREBASE_PROJECT_ID="internstore-dev"
CURL="curl -sk"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

login() {
  curl -sf -X POST "$FIREBASE_AUTH_EMULATOR_URL/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$1\",\"password\":\"$2\",\"returnSecureToken\":true}" | jq -r .idToken
}

# STR-150: /checkout/v2 computes its charge amount from Catalog's real
# price for each cart product_id (orders/routers/checkout_v2.py ->
# CatalogClient.get_product_price -> GET /products/:id) -- unlike the
# Kafka-choreographed v1 checkout (scripts/test-reservation-saga.sh),
# which never looks the product up in Catalog at all. This script used to
# generate PRODUCT_A/PRODUCT_B as bare `uuid.uuid4()`s that exist in
# Inventory (via seed_stock) but not in Catalog -- GET /products/:id 404s,
# uncaught, and checkout/v2 500s before a workflow is even started. Never
# caught locally because it depends on exactly which script you happen to
# reach for. Fixed by actually creating a real Catalog product (with a
# controlled price) for each one, instead of assuming an ambient product
# would exist or that the demo seed data would happen to contain a ".99"
# price for section 2.
create_catalog_product() {
  # $1 = admin token, $2 = price -> product_id
  local category_id product_id
  category_id=$($CURL "$CATALOG_URL/categories" -H "Authorization: Bearer $1" | jq -r '.[0].id')
  [ -n "$category_id" ] && [ "$category_id" != "null" ] || fail "create_catalog_product: no categories exist in Catalog"
  product_id=$($CURL -X POST "$CATALOG_URL/products" -H "Authorization: Bearer $1" -H "Content-Type: application/json" \
    -d "{\"name\": \"Temporal saga smoke product $$-$RANDOM\", \"price\": $2, \"category_id\": \"$category_id\"}" | jq -r .id)
  [ -n "$product_id" ] && [ "$product_id" != "null" ] || fail "create_catalog_product: could not create product"
  echo "$product_id"
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

# Queries Temporal's workflow history and asserts every name in $2
# (space-separated) appears somewhere in the history — a cheap but real
# check that the expected activities actually ran, not just that the
# workflow finished.
#
# STR-150: was `docker run --rm --network ... temporalio/admin-tools:
# 1.27.2-tctl-1.18.2-cli-1.1.1 temporal workflow show ...` -- that pinned
# tag isn't present locally and this environment has no egress to pull it
# ("Unable to find image ... not found"), so this always failed before
# ever reaching a real assertion. The `temporal` service container
# already bundles the same `temporal` CLI (it's how temporal-ui/checkout-
# workflow-worker's own tooling works) and sits on the compose network
# already, so `docker compose exec` into it instead of spinning up a
# separate throwaway container -- no extra image, no pull, one less moving
# part.
#
# STR-151: `--detailed`'s table output never contains activity type names
# at all -- just event kinds (ActivityTaskScheduled, ActivityTaskCompleted,
# ...) with no indication of *which* activity. This assertion could never
# have passed as written. Found already fixed in
# scripts/k8s/test-temporal-saga.sh (STR-145), which uses `--output json`
# to surface the real `activityType.name` field; ported back here.
assert_workflow_history_contains() {
  local workflow_id="$1" expected_names="$2"
  local history
  history=$(docker compose exec -T temporal temporal workflow show \
    --address temporal:7233 --workflow-id "$workflow_id" --output json 2>&1) \
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
# price 10.00 * quantity 3 = 30.00 -- deliberately not a ".99" total, so
# the happy path doesn't accidentally trip Payments' failure simulation.
PRODUCT_A=$(create_catalog_product "$ADMIN_TOKEN" 10.00)
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
# Payments' dev-only failure simulation fails any charge whose amount
# formatted to 2dp ends in PAYMENT_FAIL_ON_AMOUNT_SUFFIX (default "99",
# see payments/routers/payments.py's _simulate_outcome and
# services/payments/README.md). price 12.99 * quantity 1 = 12.99 hits it
# deterministically, instead of assuming the demo catalog seed happens to
# contain a ".99"-priced product.
PRODUCT_B=$(create_catalog_product "$ADMIN_TOKEN" 12.99)
seed_stock "$ADMIN_TOKEN" "$PRODUCT_B" 5

$CURL -X POST "$GATEWAY_URL/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_B\", \"quantity\": 1}" >/dev/null

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
