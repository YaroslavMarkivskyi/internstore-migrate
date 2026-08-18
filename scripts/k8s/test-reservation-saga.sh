#!/usr/bin/env bash
# K8s-adapted copy of scripts/test-reservation-saga.sh (STR-145). This
# script has no `docker compose exec`/`docker compose logs` calls to
# translate -- it only talks to the stack over HTTP through the gateway,
# which already works unmodified against nginx's NodePort. Copied here
# anyway (rather than pointed at directly) so all in-scope saga scripts
# have a single k8s/ home, and so the two real bugs found while actually
# running it (below) don't have to be re-discovered by whoever reaches
# for it next. The compose original remains the source of truth for
# local docker-compose dev; this file is not meant to replace it. If you
# fix a bug here, check whether the same bug exists in the compose
# original too -- see STR-151, which found fixes made in one copy that
# were never ported to the other.
#
# End-to-end verification of the reservation saga (Orders outbox + Inventory
# idempotent consumer) through the real gateway, real Firebase-issued
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
#   3. Expired reservation -> cancelled, using inventory's actual
#      RESERVATION_TTL_SECONDS/RESERVATION_CHECK_INTERVAL_SECONDS.
#
# Requires: curl, jq, python3, kubectl. Run after
# `kubectl apply -k k8s/overlays/local/` with every pod Running/Ready.
# Assumes nginx's NodePort (30843->8443) is reachable at localhost via
# k8s/kind-config.yaml. STR-192: Keycloak's own NodePort is gone along
# with the Deployment -- k8s/overlays/local has no Firebase Auth emulator
# of its own (that's docker-compose.yml-only, see firebase/README.md), so
# login() below assumes one is separately reachable at localhost:9099
# (e.g. `docker compose up -d firebase-emulator` run alongside this kind
# cluster) rather than anything k8s/ itself provides.
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
    # STR-145: was `actual=$(eval "$check_cmd")` with no `|| true` -- under
    # `set -e`, a single transient hiccup mid-poll (a momentary non-JSON
    # response from a pod that's still starting/restarting, tripping jq's
    # own parse error inside $check_cmd) makes this assignment's nonzero
    # exit status kill the *entire script*, not just this one poll
    # attempt -- silently, with no FAIL line, well before the timeout is
    # reached. Caught here because k8s pods restarting mid-poll is more
    # visible than compose's steadier containers, but the underlying bug
    # is in this function, not anything k8s-specific -- it would kill the
    # compose original the same way given the same transient blip.
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

echo "=== 3. Expired reservation -> cancelled ==="
PRODUCT_C=$(python3 -c "import uuid; print(uuid.uuid4())")
seed_stock "$ADMIN_TOKEN" "$PRODUCT_C" 5

$CURL -X POST "$GATEWAY_URL/cart" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_C\", \"quantity\": 2}" >/dev/null
ORDER_C=$($CURL -X POST "$GATEWAY_URL/checkout" -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d '{"contact_name": "Saga Customer", "contact_email": "customer@example.com", "payment_method": "card"}' | jq -r .id)
[ -n "$ORDER_C" ] && [ "$ORDER_C" != "null" ] || fail "checkout for product C did not return an order id"
poll_until 30 "order_status '$CUSTOMER_TOKEN' '$ORDER_C'" "pending" "order C reserved -> pending"

# Deliberately never paid.
#
# STR-145: the compose original polls for cancellation with only a 60s
# timeout and a comment claiming RESERVATION_TTL_SECONDS=30 -- but both
# docker-compose.yml and k8s/base/inventory/configmap.yaml actually set it
# to 300s (confirmed against the live inventory pod's own env), so the
# original script's 60s poll can never succeed in either environment; this
# looks like a stale comment/timeout left over from before the TTL was
# bumped from 30s to 300s (see inventory's compose comment: "300s instead
# of the original 30s so manually clicking through checkout -> pay ...
# doesn't race the expiry checker"). Not a k8s-specific issue -- flagging
# it for the compose original too. Timeout bumped to the real TTL (300s)
# plus a buffer for the 5s check interval and general poll slack.
#
# STR-145: bumping that timeout to 330s surfaced a second, compounding
# real bug under Keycloak (confirmed live: `GET /admin/realms/internstore`
# -> accessTokenLifespan: 300): CUSTOMER_TOKEN minted once near the top of
# the script and reused for the rest of the run could expire *during* this
# poll, with every subsequent order_status call 401ing (nginx's own
# auth_request-rejection error page, not JSON, so jq fails to parse it) for
# the rest of the window -- indistinguishable from a hung saga without
# checking the raw response. Not k8s-specific either; the original's fast
# 60s poll (paired with its incorrect 30s-TTL assumption) never ran long
# enough to hit this. STR-192: Firebase ID tokens default to a 1h
# lifespan, well clear of this poll's ~300s window, but the
# re-login-per-poll fix is kept anyway -- still correct, and it's one less
# assumption about token lifetime for this poll to depend on.
order_status_fresh() {
  local fresh_token
  fresh_token=$(login "customer@example.com" "Customer123")
  order_status "$fresh_token" "$1"
}
poll_until 330 "order_status_fresh '$ORDER_C'" "cancelled" \
  "reservation TTL (300s) expires -> ReservationExpired -> (real Kafka) -> status=cancelled"

# Same expiry risk as CUSTOMER_TOKEN above -- by this point the script has
# comfortably run past ADMIN_TOKEN's own 300s lifespan too, so it's
# refreshed here rather than reused.
ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
poll_until 15 "item_quantity '$ADMIN_TOKEN' '$PRODUCT_C'" "5" \
  "expiry released reserved_quantity -> quantity back to 5 (never actually decremented)"

echo
echo "All reservation-saga verification checks passed against the real Kafka broker."
