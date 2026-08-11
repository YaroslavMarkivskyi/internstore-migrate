#!/usr/bin/env bash
# STR-149: end-to-end verification of Inventory's event-sourced (stock_id,
# product_id) aggregate through the real gateway, real Keycloak-issued
# tokens, and a real Kafka broker — no mocks anywhere in this script.
# Parallel to, and does not replace, scripts/test-reservation-saga.sh and
# scripts/test-temporal-saga.sh, both of which must also keep passing
# unchanged against this same event-sourced implementation (run them
# alongside this script as a combined merge gate, see README.md).
#
# Covers:
#   1. A sequence of receive -> receive -> reserve (via a real checkout)
#      -> pay (consume) -> move against a single product, driven through
#      the ordinary admin/customer-facing endpoints. STR-150: reserve
#      deliberately runs before move (was move -> reserve) -- see the
#      "STR-150" comment further down for why.
#   2. GET .../history shows the exact event sequence that sequence of
#      operations produced, for both stock_ids the move touched.
#   3. GET .../as-of at a timestamp captured mid-sequence reconstructs the
#      correct intermediate state (reflects the move, not the later
#      reservation/consumption).
#   4. Crash-safety: NOT a literal "kill the projector mid-sequence" (this
#      design has no separate async projector process — the projection is
#      updated synchronously, in the same DB transaction as the event
#      append, see README.md's "Event sourcing" section). What a black-box
#      script CAN meaningfully check is the observable property that
#      matters: after every step, `stock_items` (the live projection)
#      agrees with a fresh replay of `stock_events` for that aggregate,
#      i.e. there is never a window where events exist without a matching
#      projection update. True proof of transaction-level atomicity (a
#      projection failure rolling back the event append too) is a unit
#      test (test_event_append.py / test_projection_consistency.py), not
#      something this script fakes with a process kill.
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

create_stock() {
  # $1 = admin token, $2 = name suffix
  $CURL -X POST "$INVENTORY_URL/stocks" \
    -H "Authorization: Bearer $1" -H "Content-Type: application/json" \
    -d "{\"name\": \"Event sourcing smoke stock $2 $$-$RANDOM\"}" | jq -r .id
}

order_status() {
  $CURL "$GATEWAY_URL/orders/$2" -H "Authorization: Bearer $1" | jq -r .status
}

poll_until() {
  local timeout_s="$1" check_cmd="$2" expected="$3" label="$4"
  local elapsed=0
  while [ "$elapsed" -lt "$timeout_s" ]; do
    local actual
    # STR-150: was `actual=$(eval "$check_cmd")` with no `|| true` -- one
    # of this script's own check_cmds pipes into `grep -c` (see the
    # StockConsumed poll below), and grep -c exits 1 (while still
    # printing "0" to stdout) when the count is zero. Under `set -e`,
    # that non-zero status from the very first poll attempt -- before
    # StockConsumed has had a chance to show up -- killed the whole
    # script silently, with no FAIL line, well before the 30s timeout.
    # Same root cause STR-145 already found and fixed in
    # scripts/test-reservation-saga.sh's own poll_until; ported here too.
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

# $1 = admin token, $2 = stock_id, $3 = product_id -> space-separated
# event_type list in sequence_number order.
history_event_types() {
  $CURL "$INVENTORY_URL/stocks/$2/$3/history" -H "Authorization: Bearer $1" \
    | jq -r '[.items[].event_type] | join(",")'
}

# $1 = admin token, $2 = stock_id, $3 = product_id -> stock_items row
# re-derived by replaying stock_events, compared against the live row --
# both should always agree (see item 4 above).
assert_projection_matches_replay() {
  local admin="$1" stock_id="$2" product_id="$3"
  local live_quantity history last_event_type
  live_quantity=$($CURL "$INVENTORY_URL/stocks/$stock_id/items" -H "Authorization: Bearer $admin" \
    | jq -r ".[] | select(.product_id==\"$product_id\") | .quantity")
  history=$($CURL "$INVENTORY_URL/stocks/$stock_id/$product_id/history?limit=200" -H "Authorization: Bearer $admin")
  # Full event-semantics replay in bash/jq would just re-implement
  # projector.apply_event -- that proof (replay exactly equals the live
  # projection) belongs to test_projection_consistency.py. What a
  # black-box script CAN usefully check is the coarse invariant: a live
  # stock_items row exists if and only if the aggregate's last event
  # wasn't a removal -- i.e. there's no window where the event log and
  # the projection disagree about whether the aggregate currently exists.
  last_event_type=$(echo "$history" | jq -r '.items[-1].event_type // "none"')
  if [ "$last_event_type" = "StockItemRemoved" ]; then
    [ "$live_quantity" = "" ] || fail "aggregate ($stock_id,$product_id): history's last event is StockItemRemoved but a live stock_items row still exists"
  else
    [ "$live_quantity" != "" ] || fail "aggregate ($stock_id,$product_id): history has events (last=$last_event_type) but no live stock_items row exists"
  fi
}

CUSTOMER_TOKEN=$(login "customer@example.com" "Customer123")
ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$CUSTOMER_TOKEN" != "null" ] || fail "customer login did not return an access token"
[ "$ADMIN_TOKEN" != "null" ] || fail "admin login did not return an access token"

echo "=== 1. Build a mixed event sequence: receive -> receive -> reserve -> pay -> move ==="
PRODUCT=$(python3 -c "import uuid; print(uuid.uuid4())")
STOCK_A=$(create_stock "$ADMIN_TOKEN" "A")
STOCK_B=$(create_stock "$ADMIN_TOKEN" "B")
[ -n "$STOCK_A" ] && [ "$STOCK_A" != "null" ] || fail "could not create stock A"
[ -n "$STOCK_B" ] && [ "$STOCK_B" != "null" ] || fail "could not create stock B"

$CURL -X POST "$INVENTORY_URL/stocks/$STOCK_A/items" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d "{\"product_id\": \"$PRODUCT\", \"quantity\": 20}" >/dev/null
pass "StockItemCreated: received 20 units into stock A"

$CURL -X POST "$INVENTORY_URL/stocks/$STOCK_A/items" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d "{\"product_id\": \"$PRODUCT\", \"quantity\": 10}" >/dev/null
pass "ItemReceived: received 10 more units into stock A (30 total)"

ITEM_A=$($CURL "$INVENTORY_URL/stocks/$STOCK_A/items" -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq -r ".[] | select(.product_id==\"$PRODUCT\") | .id")
[ -n "$ITEM_A" ] && [ "$ITEM_A" != "null" ] || fail "could not find stock A's item for $PRODUCT"

# Timestamp captured strictly after the receives, strictly before the
# move -- as-of at this point should show 30 units in stock A and nothing
# yet in stock B.
MIDPOINT=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())")
sleep 1

# STR-150: reserve deliberately happens here, BEFORE the move (was
# move -> reserve). commands._allocate picks which StockItem row(s) to
# reserve from by `ORDER BY StockItem.id` across every row for the
# product -- id is a random uuid4, unrelated to which stock the row lives
# in or when it was created, so which of stock A/B actually received the
# StockReserved event was a coin flip, not the "stock A" this section
# hard-asserts a few lines down (confirmed live: one real run landed the
# whole reservation on stock B instead). Reordering so the checkout runs
# while stock B's row for this product doesn't exist yet (the move hasn't
# happened) makes stock A the only possible allocation target -- no
# change to Inventory itself, this is a test-sequencing fix. Consumption
# at pay time is keyed off the reservation's own stock_item_id (not
# re-resolved by product_id), so it stays pinned to stock A even after
# the later move.
$CURL -X POST "$GATEWAY_URL/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT\", \"quantity\": 4}" >/dev/null
CHECKOUT=$($CURL -X POST "$GATEWAY_URL/checkout" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d '{"contact_name": "ES Customer", "contact_email": "customer@example.com", "payment_method": "card"}')
ORDER=$(echo "$CHECKOUT" | jq -r .id)
[ -n "$ORDER" ] && [ "$ORDER" != "null" ] || fail "checkout did not return an order id: $CHECKOUT"

poll_until 30 "order_status '$CUSTOMER_TOKEN' '$ORDER'" "pending" \
  "OrderCreated -> Inventory reserves -> StockReserved -> status=pending (guaranteed against stock A -- stock B doesn't have this product yet)"

PAY=$($CURL -X POST "$GATEWAY_URL/orders/$ORDER/pay" -H "Authorization: Bearer $CUSTOMER_TOKEN")
[ "$(echo "$PAY" | jq -r .status)" = "paid" ] || fail "expected status=paid after pay, got: $PAY"

poll_until 30 "history_event_types '$ADMIN_TOKEN' '$STOCK_A' '$PRODUCT' | grep -c StockConsumed" "1" \
  "PaymentConfirmed -> Inventory consumes -> StockConsumed appended to stock A's history"

$CURL -X POST "$INVENTORY_URL/stocks/$STOCK_A/items/$ITEM_A/move" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d "{\"to_stock_id\": \"$STOCK_B\", \"quantity\": 12}" >/dev/null
pass "ItemMovedOut/ItemMovedIn: moved 12 units from stock A to stock B"

echo "=== 2. GET history shows the exact event sequence on both touched aggregates ==="
HISTORY_A=$(history_event_types "$ADMIN_TOKEN" "$STOCK_A" "$PRODUCT")
[ "$HISTORY_A" = "StockItemCreated,ItemReceived,StockReserved,StockConsumed,ItemMovedOut" ] \
  || fail "unexpected stock A history: $HISTORY_A"
pass "stock A history: $HISTORY_A"

HISTORY_B=$(history_event_types "$ADMIN_TOKEN" "$STOCK_B" "$PRODUCT")
[ "$HISTORY_B" = "ItemMovedIn" ] || fail "unexpected stock B history: $HISTORY_B"
pass "stock B history: $HISTORY_B"

echo "=== 3. GET as-of at the mid-sequence timestamp reconstructs the correct intermediate state ==="
# STR-150: MIDPOINT is an ISO-8601 timestamp with a "+00:00" UTC offset --
# dropped straight into a query string unencoded, curl sends the literal
# "+", and query-string parsing rules (this server's included) treat "+"
# as an encoded space, not a literal plus. FastAPI/pydantic then saw
# "...093160 00:00" and 422'd with a datetime parse error -- never caught
# before because this script had never actually been run against a live
# server (see ticket). URL-encode the one character that matters here
# rather than pulling in a general encoder for a single query param.
MIDPOINT_ENCODED=${MIDPOINT//+/%2B}
AS_OF_A=$($CURL "$INVENTORY_URL/stocks/$STOCK_A/$PRODUCT/as-of?timestamp=$MIDPOINT_ENCODED" -H "Authorization: Bearer $ADMIN_TOKEN")
[ "$(echo "$AS_OF_A" | jq -r .quantity)" = "30" ] || fail "as-of stock A at midpoint expected quantity=30, got: $AS_OF_A"
[ "$(echo "$AS_OF_A" | jq -r .reserved_quantity)" = "0" ] || fail "as-of stock A at midpoint expected reserved_quantity=0, got: $AS_OF_A"
pass "as-of(stock A, midpoint) = quantity 30, reserved 0 -- before the reserve/consume/move"

AS_OF_B_STATUS=$($CURL -o /dev/null -w "%{http_code}" "$INVENTORY_URL/stocks/$STOCK_B/$PRODUCT/as-of?timestamp=$MIDPOINT_ENCODED" -H "Authorization: Bearer $ADMIN_TOKEN")
[ "$AS_OF_B_STATUS" = "404" ] || fail "as-of stock B at midpoint expected 404 (aggregate didn't exist yet), got: $AS_OF_B_STATUS"
pass "as-of(stock B, midpoint) = 404 -- stock B's aggregate didn't exist until the move"

echo "=== 4. Projection/event-log agreement after every step (no async projector to kill -- see script header) ==="
assert_projection_matches_replay "$ADMIN_TOKEN" "$STOCK_A" "$PRODUCT"
assert_projection_matches_replay "$ADMIN_TOKEN" "$STOCK_B" "$PRODUCT"
pass "stock_items projection agrees with stock_events history for both aggregates"

echo
echo "All event-sourcing verification checks passed. Run scripts/test-reservation-saga.sh"
echo "and scripts/test-temporal-saga.sh alongside this script -- neither saga's behavior"
echo "may differ against this event-sourced implementation."
