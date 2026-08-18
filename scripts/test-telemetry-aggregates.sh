#!/usr/bin/env bash
# End-to-end verification of the telemetry-aggregates CQRS read model
# (STR-147) through the real gateway, real Firebase-issued tokens, and a
# real Kafka broker — no mocks anywhere in this script.
#
# Covers:
#   1. Seed a store/product pair (same Catalog/Inventory flow as
#      test-telemetry-saga.sh) so Telemetry has a store_product_thresholds
#      row to fan TemperatureRecorded out to.
#   2. POST several measurements -> Telemetry's outbox stages
#      TemperatureRecorded -> (real Kafka) -> telemetry-aggregates'
#      incremental consumer updates hourly_aggregates. Verified via
#      GET /aggregates/... within seconds.
#   3. Stop telemetry-aggregates (simulating consumer downtime), publish
#      more measurements (these still land in telemetry-db's raw table —
#      Telemetry itself is unaffected — but telemetry-aggregates never
#      sees the corresponding events while it's down).
#   4. Restart telemetry-aggregates and wait past one backfill cycle
#      (BACKFILL_INTERVAL_MINUTES=0.2 in docker-compose.yml, a dev/test
#      override of the realistic 15-minute default — see that file).
#      Verify the aggregate matches the true average computed from every
#      measurement sent, proving the read model self-corrected.
#
# Requires: curl, jq, python3, docker compose. Run after
# `docker compose up -d --build` (needs kafka, kafka-topic-init, catalog,
# inventory, telemetry, telemetry-aggregates, nginx, firebase-emulator all healthy).
set -euo pipefail

FIREBASE_AUTH_EMULATOR_URL="http://localhost:9099"
CATALOG_URL="https://localhost:8443/api/catalog"
INVENTORY_URL="https://localhost:8443/api/inventory"
TELEMETRY_URL="https://localhost:8443/api/telemetry"
AGGREGATES_URL="https://localhost:8443/api/telemetry-aggregates"
FIREBASE_PROJECT_ID="internstore-dev"
CURL="curl -sk"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

login() {
  curl -sf -X POST "$FIREBASE_AUTH_EMULATOR_URL/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$1\",\"password\":\"$2\",\"returnSecureToken\":true}" | jq -r .idToken
}

poll_until() {
  local timeout_s="$1" check_cmd="$2" expected="$3" label="$4"
  local elapsed=0 actual=""
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

ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$ADMIN_TOKEN" != "null" ] || fail "admin login did not return an access token"

echo "=== 1. Seed a product + a stock carrying it (ItemAdded -> Telemetry's store_product_thresholds) ==="
CATEGORY_ID=$($CURL -X POST "$CATALOG_URL/categories" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d '{"name": "Cold Chain"}' | jq -r '.id // empty')
if [ -z "$CATEGORY_ID" ]; then
  # Category may already exist from a previous run — reuse it (same
  # resilience pattern as test-shopping-agent.sh).
  CATEGORY_ID=$($CURL "$CATALOG_URL/categories" -H "Authorization: Bearer $ADMIN_TOKEN" \
    | jq -r '.[] | select(.name == "Cold Chain") | .id' | head -n1)
fi
[ -n "$CATEGORY_ID" ] && [ "$CATEGORY_ID" != "null" ] || fail "could not create or find a Cold Chain category"

PRODUCT_ID=$($CURL -X POST "$CATALOG_URL/products" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"Aggregates smoke milk\", \"price\": 1.5, \"category_id\": \"$CATEGORY_ID\"}" | jq -r .id)
[ -n "$PRODUCT_ID" ] && [ "$PRODUCT_ID" != "null" ] || fail "could not create product"

STOCK_ID=$($CURL -X POST "$INVENTORY_URL/stocks" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d "{\"name\": \"Aggregates smoke stock $$-$RANDOM\"}" | jq -r .id)
[ -n "$STOCK_ID" ] && [ "$STOCK_ID" != "null" ] || fail "could not create stock"

$CURL -X POST "$INVENTORY_URL/stocks/$STOCK_ID/items" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d "{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 10}" >/dev/null
pass "stock $STOCK_ID now carries product $PRODUCT_ID -> ItemAdded published"

sleep 5  # let Telemetry's inventory-events consumer create the store_product_thresholds row

send_reading() {
  $CURL -X POST "$TELEMETRY_URL/measurements" -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" -d "{\"store_id\": \"$STOCK_ID\", \"temperature\": $1}" >/dev/null
}

aggregate_json() {
  $CURL "$AGGREGATES_URL/aggregates/$STOCK_ID/$PRODUCT_ID?period=week" -H "Authorization: Bearer $ADMIN_TOKEN"
}

# Tolerates transient non-JSON responses (e.g. nginx 502 in the brief
# window right after `docker compose start` before the upstream is
# actually accepting connections) by falling back to "0" instead of
# letting jq's parse error kill the whole script under `set -o
# pipefail` — poll_until needs this to be able to retry.
reading_count() {
  local body
  body=$(aggregate_json)
  echo "$body" | jq '[.[].reading_count] | add // 0' 2>/dev/null || echo "0"
}

echo "=== 2. Incremental path: send readings, verify GET /aggregates reflects them within seconds ==="
FIRST_BATCH=(4.0 5.0 6.0)
for t in "${FIRST_BATCH[@]}"; do send_reading "$t"; done
pass "sent ${#FIRST_BATCH[@]} readings -> ${#FIRST_BATCH[@]} TemperatureRecorded events staged"

poll_until 30 "reading_count" "${#FIRST_BATCH[@]}" \
  "telemetry-aggregates' incremental consumer reflects all sent readings"

echo "=== 3. Simulate consumer downtime: stop telemetry-aggregates, send more readings ==="
docker compose stop telemetry-aggregates >/dev/null
pass "telemetry-aggregates stopped"

SECOND_BATCH=(9.0 3.0)
for t in "${SECOND_BATCH[@]}"; do send_reading "$t"; done
pass "sent ${#SECOND_BATCH[@]} more readings while telemetry-aggregates is down (still land in telemetry-db raw table)"

TOTAL_COUNT=$(( ${#FIRST_BATCH[@]} + ${#SECOND_BATCH[@]} ))
# Not checked here: querying GET /aggregates while telemetry-aggregates
# itself is stopped can't return anything meaningful (nginx 502s, not
# valid JSON) — the "still stale" property is inherent to the scenario,
# not something worth asserting via the very endpoint that's down.

echo "=== 4. Restart, wait past a backfill cycle, verify self-correction to the true average ==="
RESTART_TS=$(date +%s)
docker compose start telemetry-aggregates >/dev/null
pass "telemetry-aggregates restarted"

poll_until 60 "reading_count" "$TOTAL_COUNT" \
  "aggregate self-corrected to include all $TOTAL_COUNT readings (incremental catch-up and/or backfill)"
CONVERGED_TS=$(date +%s)
echo "INFO: convergence took $((CONVERGED_TS - RESTART_TS))s after restart (BACKFILL_INTERVAL_MINUTES=0.2, i.e. 12s, in docker-compose.yml's dev override)"

ALL_TEMPS=("${FIRST_BATCH[@]}" "${SECOND_BATCH[@]}")
TRUE_AVG=$(python3 -c "print(sum([${ALL_TEMPS[*]/%/,}]) / $TOTAL_COUNT)")
GOT_AVG=$(aggregate_json | jq '(([.[] | .avg_temperature * .reading_count] | add) / ([.[] | .reading_count] | add))')
python3 -c "import sys; a, b = float('$TRUE_AVG'), float('$GOT_AVG'); sys.exit(0 if abs(a - b) < 0.01 else 1)" \
  || fail "aggregate avg ($GOT_AVG) does not match true raw-data average ($TRUE_AVG)"
pass "aggregate average ($GOT_AVG) matches true raw-data average ($TRUE_AVG)"

echo
echo "All telemetry-aggregates verification checks passed against the real Kafka broker."
