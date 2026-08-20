#!/usr/bin/env bash
# K8s-adapted copy of scripts/test-temporal-saga.sh (STR-145). The
# compose original's `docker run --network ... temporalio/admin-tools`
# calls (for querying workflow history) become `kubectl run` one-shot
# pods addressing temporal:7233 via in-cluster DNS. The compose original
# remains the source of truth for local docker-compose dev; this file is
# not meant to replace it. If you fix a bug here, check whether the same
# bug exists in the compose original too -- see STR-151, which found
# fixes made in one copy that were never ported to the other.
#
# End-to-end verification of the Temporal-orchestrated checkout
# (STR-139) through the real gateway, real Firebase-issued tokens, a real
# Temporal server, and a real Kafka broker (for the escalation/fan-out
# side) — no mocks anywhere in this script. Parallel to, and does not
# replace, scripts/k8s/test-reservation-saga.sh (the existing Kafka-
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
#   3. Uses a throwaway temporalio/admin-tools pod to query workflow
#      history and assert the expected activity sequence appears.
#
# STR-145: the compose original assumes "the demo catalog has at least
# one product priced to land on a .99 total" for both PRODUCT_A and
# PRODUCT_B, but never actually registers either product in Catalog --
# checkout_v2.py's own price lookup (`catalog_client.get_product_price`,
# added for STR-139 specifically so prices are "never trusted from the
# client") means *both* products need a real Catalog row with a known
# price, or checkout/v2 fails at the price-lookup step before ever
# reaching Payments. This is why the original script's suffix-matching
# comment ("assumes... adjust PRODUCT_B's price in Catalog first") reads
# like a manual step nobody automated -- caught here because this is the
# first time the script has actually been run end-to-end. Fixed below by
# registering both products in Catalog with prices chosen to hit the
# intended happy-path/failure outcomes deterministically, instead of
# relying on whatever the demo seed data happens to contain.
#
# Requires: curl, jq, python3, kubectl. Run after
# `kubectl apply -k k8s/overlays/local/` with every pod Running/Ready
# (needs temporal, temporal-db, temporal-ui, payments, checkout-workflow-worker,
# orders, inventory, catalog, nginx, kafka all healthy -- see login() comment above).
set -euo pipefail

# STR-192: k8s/overlays/local has no Firebase Auth emulator of its own
# (that's docker-compose.yml-only, see firebase/README.md) -- assumes one
# is separately reachable at localhost:9099.
FIREBASE_AUTH_EMULATOR_URL="http://localhost:9099"
CATALOG_URL="https://localhost:8443/api/catalog"
GATEWAY_URL="https://localhost:8443/api/orders"
INVENTORY_URL="https://localhost:8443/api/inventory"
FIREBASE_PROJECT_ID="internstore-dev"
CURL="curl -sk"
# STR-145: the compose original's tag
# ("1.27.2-tctl-1.18.2-cli-1.1.1") no longer exists on Docker Hub
# (confirmed live: `docker pull` 404s with "not found") -- caught here
# because this is the first time the script has actually been run.
# `:latest`'s `temporal` CLI is backwards-compatible with the 1.27.2
# server this stack runs (Temporal's CLI/server compatibility policy),
# confirmed working against this cluster below. Worth fixing in the
# compose original too, not just here.
ADMIN_TOOLS_IMAGE="temporalio/admin-tools:latest"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

login() {
  curl -sf -X POST "$FIREBASE_AUTH_EMULATOR_URL/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$1\",\"password\":\"$2\",\"returnSecureToken\":true}" | jq -r .idToken
}

# $1 = admin token, $2 = category id, $3 = price -> prints product id
seed_product() {
  $CURL -X POST "$CATALOG_URL/products" -H "Authorization: Bearer $1" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"Temporal saga smoke product $$-$RANDOM\", \"price\": $3, \"category_id\": \"$2\"}" \
    | jq -r .id
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
    actual=$(eval "$check_cmd" 2>/dev/null) || actual="<poll error, retrying>"
    if [ "$actual" = "$expected" ]; then
      pass "$label (took ~${elapsed}s)"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  fail "$label: timed out after ${timeout_s}s waiting for '$expected', last saw '$actual'"
}

# Queries Temporal's workflow history via a throwaway admin-tools pod
# in-cluster (this script itself runs on the host, outside the cluster
# network) and asserts every name in $2 (space-separated) appears
# somewhere in the history — a cheap but real check that the expected
# activities actually ran, not just that the workflow finished.
#
# STR-145: the compose original's default `temporal workflow show` table
# output never contains activity type names at all -- just event kinds
# like "ActivityTaskScheduled"/"ActivityTaskCompleted" with no indication
# of *which* activity. This assertion could never have passed as written,
# against either environment; caught here because this is the first time
# the script has actually been run. `--output json` surfaces the real
# `activityType.name` field (confirmed live: reserve_stock, create_order,
# charge_payment, etc. all present) that the grep below actually needs.
assert_workflow_history_contains() {
  local workflow_id="$1" expected_names="$2"
  local pod_name="temporal-history-$$-$RANDOM"
  local history
  # `-i` (attach stdin) was silently truncating captured output when this
  # script runs backgrounded/non-interactively (no TTY) -- dropped since
  # nothing here needs stdin, only the one-shot command's stdout.
  history=$(kubectl run "$pod_name" --image="$ADMIN_TOOLS_IMAGE" --restart=Never --rm --attach \
    --command -- temporal workflow show --address temporal.default.svc.cluster.local:7233 --workflow-id "$workflow_id" --output json 2>&1) \
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

CATEGORY_ID=$($CURL -X POST "$CATALOG_URL/categories" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d "{\"name\": \"TS-$RANDOM\"}" | jq -r .id)
[ -n "$CATEGORY_ID" ] && [ "$CATEGORY_ID" != "null" ] || fail "could not create category"

echo "=== 1. Happy path: /checkout/v2 -> reserve -> order -> charge -> paid ==="
# Price deliberately NOT ending in .99 (Payments' dev-only failure
# simulation, PAYMENT_FAIL_ON_AMOUNT_SUFFIX="99") x quantity 3 = 28.50.
PRODUCT_A=$(seed_product "$ADMIN_TOKEN" "$CATEGORY_ID" "9.50")
[ -n "$PRODUCT_A" ] && [ "$PRODUCT_A" != "null" ] || fail "could not create product A"
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
# Price x quantity deliberately ends in .99 (12.99 x 1) to trip Payments'
# dev-only failure simulation.
PRODUCT_B=$(seed_product "$ADMIN_TOKEN" "$CATEGORY_ID" "12.99")
[ -n "$PRODUCT_B" ] && [ "$PRODUCT_B" != "null" ] || fail "could not create product B"
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
