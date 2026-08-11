#!/usr/bin/env bash
# K8s-adapted copy of scripts/test-telemetry-saga.sh (STR-145). No
# `docker compose exec`/`logs` calls to translate — the only compose
# dependency here is Mailpit, which k8s/base deliberately excludes (dev-
# only, no K8s equivalent — see k8s/README.md). Per this ticket: stand up
# a throwaway Mailpit Deployment+Service for this one check rather than
# building real SMTP infra. Before running this script:
#
#   kubectl create deployment mailpit --image=axllent/mailpit:v1.20 --port=8025
#   kubectl apply -f - <<'EOF'
#   apiVersion: v1
#   kind: Service
#   metadata:
#     name: mailpit
#     labels: {app: mailpit}
#   spec:
#     selector: {app: mailpit}
#     ports:
#     - {name: http, port: 8025, targetPort: 8025}
#     - {name: smtp, port: 1025, targetPort: 1025}
#   EOF
#   kubectl rollout restart deployment/notifications   # picks up the now-resolvable "mailpit" host
#   kubectl port-forward svc/mailpit 8025:8025 &        # exposes Mailpit's REST API at localhost:8025 below
#
# Notifications' SMTP_HOST/SMTP_PORT ConfigMap values already point at
# "mailpit:1025" (mirroring compose) even though nothing backs that
# hostname by default — this throwaway Deployment+Service is the only
# thing missing, not a config change.
#
# Teardown when done: `kubectl delete deployment,service mailpit` (and
# kill the port-forward). Not left running as part of the normal stack.
#
# The compose original remains the source of truth for local
# docker-compose dev; this file is not meant to replace it.
#
# End-to-end verification of the telemetry saga (Telemetry violation
# detection + outbox -> Inventory idempotent consumer -> Notifications
# email) through the real gateway, real Keycloak-issued tokens, and a real
# Kafka broker — no mocks anywhere in this script.
#
# Covers the full chain:
#   1. Inventory ItemAdded (real Kafka) -> Telemetry caches
#      {store_id, product_id} in store_product_thresholds.
#   2. Catalog ProductThresholdUpdated (real Kafka) -> Telemetry updates
#      that cache row's max_temp.
#   3. Sustained above-threshold readings -> Telemetry's violation-detection
#      background task creates an Incident and stages
#      TemperatureThresholdViolated on its outbox.
#   4. (real Kafka) -> Inventory's telemetry-events consumer sets the
#      matching StockItem.is_unavailable = true.
#   5. (real Kafka) -> Notifications sends an email, verified via Mailpit's
#      REST API.
#
# Uses VIOLATION_CHECK_INTERVAL_SECONDS=5 / VIOLATION_WINDOW_SECONDS=20 (see
# k8s/base/telemetry/configmap.yaml, mirrors docker-compose.yml) instead of
# the realistic 300s/3600s so this runs in under a minute rather than
# requiring a real hour of sustained readings.
#
# Requires: curl, jq, python3, kubectl. Run after
# `kubectl apply -k k8s/overlays/local/` with every pod Running/Ready, the
# throwaway Mailpit setup above, and its port-forward running.
set -euo pipefail

KC_URL="http://localhost:8081"
CATALOG_URL="https://localhost:8443/api/catalog"
INVENTORY_URL="https://localhost:8443/api/inventory"
TELEMETRY_URL="https://localhost:8443/api/telemetry"
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

# Searches Mailpit for a message whose subject contains $1, prints its
# message ID (empty if none found yet).
find_message_id() {
  curl -sf "$MAILPIT_URL/api/v1/search?query=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "subject:\"$1\"")" \
    | jq -r '.messages[0].ID // empty'
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

ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$ADMIN_TOKEN" != "null" ] || fail "admin login did not return an access token"

echo "=== 1. Seed a product with a low max_temperature and a stock carrying it ==="
CATEGORY_ID=$($CURL -X POST "$CATALOG_URL/categories" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d '{"name": "Dairy"}' | jq -r .id)
[ -n "$CATEGORY_ID" ] && [ "$CATEGORY_ID" != "null" ] || fail "could not create category"

PRODUCT_ID=$($CURL -X POST "$CATALOG_URL/products" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"Saga smoke milk\", \"price\": 1.5, \"category_id\": \"$CATEGORY_ID\"}" | jq -r .id)
[ -n "$PRODUCT_ID" ] && [ "$PRODUCT_ID" != "null" ] || fail "could not create product"

STOCK_ID=$($CURL -X POST "$INVENTORY_URL/stocks" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d "{\"name\": \"Saga smoke stock $$-$RANDOM\"}" | jq -r .id)
[ -n "$STOCK_ID" ] && [ "$STOCK_ID" != "null" ] || fail "could not create stock"

$CURL -X POST "$INVENTORY_URL/stocks/$STOCK_ID/items" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d "{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 10}" >/dev/null
pass "stock $STOCK_ID now carries product $PRODUCT_ID -> ItemAdded published"

sleep 5  # let Telemetry's inventory-events consumer create the cache row

$CURL -X PATCH "$CATALOG_URL/products/$PRODUCT_ID" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d '{"max_temperature": 5}' >/dev/null
pass "product max_temperature set to 5 -> ProductThresholdUpdated published"

sleep 5  # let Telemetry's catalog-events consumer update the cache row's max_temp

echo "=== 2. Sustained above-threshold readings -> violation detected ==="
$CURL -X POST "$TELEMETRY_URL/measurements" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d "{\"store_id\": \"$STOCK_ID\", \"temperature\": 15}" >/dev/null
pass "first above-threshold reading sent"

sleep 25  # exceeds VIOLATION_WINDOW_SECONDS=20 so this reading anchors the window

$CURL -X POST "$TELEMETRY_URL/measurements" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d "{\"store_id\": \"$STOCK_ID\", \"temperature\": 15}" >/dev/null
pass "second above-threshold reading sent"

incident_count() {
  $CURL "$TELEMETRY_URL/stores/$STOCK_ID/incidents" -H "Authorization: Bearer $ADMIN_TOKEN" | jq 'length'
}
poll_until 30 "incident_count" "1" \
  "sustained violation -> Telemetry creates an Incident + stages TemperatureThresholdViolated"

echo "=== 3. Inventory marks the affected item unavailable (real Kafka) ==="
item_unavailable() {
  $CURL "$INVENTORY_URL/stocks/$STOCK_ID/items" -H "Authorization: Bearer $ADMIN_TOKEN" \
    | jq -r ".[] | select(.product_id==\"$PRODUCT_ID\") | .is_unavailable"
}
poll_until 30 "item_unavailable" "true" \
  "TemperatureThresholdViolated -> (real Kafka) -> Inventory sets is_unavailable=true"

echo "=== 4. Notifications sends an email (verified via Mailpit) ==="
message_id() { find_message_id "Temperature threshold violated for stock $STOCK_ID"; }

FOUND=""
elapsed=0
while [ "$elapsed" -lt 30 ]; do
  FOUND=$(message_id)
  [ -n "$FOUND" ] && break
  sleep 2
  elapsed=$((elapsed + 2))
done
[ -n "$FOUND" ] || fail "no Mailpit message found for stock $STOCK_ID within 30s"
pass "Notifications sent an email for the violation (Mailpit message $FOUND)"

echo
echo "All telemetry-saga verification checks passed against the real Kafka broker."
