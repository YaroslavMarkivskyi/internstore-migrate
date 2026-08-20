#!/usr/bin/env bash
# End-to-end verification of inventory-gate + internal-gate + inventory-opa
# -- the sidecar chain that replaced inventory's own internal-token
# verification (services/inventory/src/inventory/auth.py's now-removed
# verify_internal_token/get_internal_claims/require_admin/require_authz).
# See scripts/verify-catalog-gate.sh, verify-security-gate.sh, and
# verify-payments-gate.sh for the same idea against those services.
#
# Inventory is the THREE-tier case, unlike the others: public read-only
# GETs, admin-only mutations + history/as-of, and identity-only (any
# authenticated role) for check-availability/reserve/release. See
# nginx/internal-gate/inventory.conf and policies/inventory.rego.
#
# Bypasses nginx (the external Gateway) the same way
# scripts/verify-gateway.sh's DIRECT() does: a throwaway container on the
# compose network hitting inventory:8000 directly, since inventory
# publishes no host port.
#
# Requires: curl, openssl, docker compose. Run after `docker compose up -d
# --build inventory inventory-opa inventory-verify inventory-gate
# inventory-db kafka`.
set -euo pipefail

NETWORK="internstore-migrate_default"
SECRET="dev-only-internal-secret-change-me"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

b64url() {
  openssl base64 -e -A | tr '+/' '-_' | tr -d '='
}

mint_token() {
  local sub="$1" role="$2" secret="$3" exp_offset="${4:-300}"
  local header='{"alg":"HS256","typ":"JWT"}'
  local now
  now=$(date +%s)
  local payload
  payload=$(printf '{"sub":"%s","role":"%s","iss":"internstore-gateway","iat":%d,"exp":%d}' "$sub" "$role" "$now" "$((now + exp_offset))")
  local signing_input
  signing_input="$(printf '%s' "$header" | b64url).$(printf '%s' "$payload" | b64url)"
  local sig
  sig=$(printf '%s' "$signing_input" | openssl dgst -sha256 -hmac "$secret" -binary | b64url)
  echo "$signing_input.$sig"
}

DIRECT() {
  docker run --rm --network "$NETWORK" curlimages/curl -s -o /dev/null -w "%{http_code}" "$@"
}

ADMIN_TOKEN=$(mint_token "admin-1" "admin" "$SECRET")
CUSTOMER_TOKEN=$(mint_token "cust-1" "customer" "$SECRET")
GUEST_TOKEN=$(mint_token "guest-1" "guest" "$SECRET")
FORGED_TOKEN=$(mint_token "attacker" "admin" "wrong-secret")

echo "=== 1. Public read-only GETs need no token ==="
STATUS=$(DIRECT http://inventory:8000/health)
[ "$STATUS" = "200" ] || fail "GET /health with no token got $STATUS, expected 200"
pass "GET /health with no token -> 200"

STATUS=$(DIRECT http://inventory:8000/items)
[ "$STATUS" = "200" ] || fail "GET /items with no token got $STATUS, expected 200"
pass "GET /items with no token -> 200"

STATUS=$(DIRECT http://inventory:8000/items/detailed)
[ "$STATUS" = "200" ] || fail "GET /items/detailed with no token got $STATUS, expected 200"
pass "GET /items/detailed with no token -> 200"

STATUS=$(DIRECT http://inventory:8000/stocks)
[ "$STATUS" = "200" ] || fail "GET /stocks with no token got $STATUS, expected 200"
pass "GET /stocks with no token -> 200"

echo "=== 2. Stock mutations are admin-only ==="
STATUS=$(DIRECT -X POST http://inventory:8000/stocks -H "Content-Type: application/json" \
  -d "{\"name\": \"gt-$RANDOM\"}")
[ "$STATUS" = "401" ] || fail "POST /stocks with no token got $STATUS, expected 401"
pass "POST /stocks with no token -> 401"

STATUS=$(DIRECT -X POST http://inventory:8000/stocks -H "Content-Type: application/json" \
  -H "X-Internal-Token: $CUSTOMER_TOKEN" \
  -d "{\"name\": \"gt-$RANDOM\"}")
[ "$STATUS" = "403" ] || fail "POST /stocks as customer got $STATUS, expected 403"
pass "POST /stocks as customer -> 403 (valid token, wrong role)"

STATUS=$(DIRECT -X POST http://inventory:8000/stocks -H "Content-Type: application/json" \
  -H "X-Internal-Token: $FORGED_TOKEN" \
  -d "{\"name\": \"gt-$RANDOM\"}")
[ "$STATUS" = "401" ] || fail "POST /stocks with forged signature got $STATUS, expected 401"
pass "POST /stocks with forged signature -> 401 (not 403 -- no valid identity)"

STOCK_NAME="gt-$RANDOM"
STOCK_BODY=$(docker run --rm --network "$NETWORK" curlimages/curl -s -X POST "http://inventory:8000/stocks" \
  -H "Content-Type: application/json" -H "X-Internal-Token: $ADMIN_TOKEN" \
  -d "{\"name\": \"$STOCK_NAME\"}")
STOCK_ID=$(echo "$STOCK_BODY" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
[ -n "$STOCK_ID" ] || fail "POST /stocks as admin did not return a stock id (body: $STOCK_BODY)"
pass "POST /stocks as admin -> 201 (id=$STOCK_ID)"

echo "=== 3. History/as-of reads are admin-only, including GET ==="
PRODUCT_ID="00000000-0000-0000-0000-000000000001"
STATUS=$(DIRECT "http://inventory:8000/stocks/$STOCK_ID/$PRODUCT_ID/history")
[ "$STATUS" = "401" ] || fail "GET .../history with no token got $STATUS, expected 401"
pass "GET .../history with no token -> 401"

STATUS=$(DIRECT "http://inventory:8000/stocks/$STOCK_ID/$PRODUCT_ID/history" -H "X-Internal-Token: $CUSTOMER_TOKEN")
[ "$STATUS" = "403" ] || fail "GET .../history as customer got $STATUS, expected 403"
pass "GET .../history as customer -> 403"

STATUS=$(DIRECT "http://inventory:8000/stocks/$STOCK_ID/$PRODUCT_ID/history" -H "X-Internal-Token: $ADMIN_TOKEN")
[ "$STATUS" = "200" ] || fail "GET .../history as admin got $STATUS, expected 200"
pass "GET .../history as admin -> 200"

echo "=== 4. check-availability/reserve/release are identity-only (any role) ==="
STATUS=$(DIRECT -X POST http://inventory:8000/stocks/check-availability -H "Content-Type: application/json" \
  -d "{\"items\": [{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 1}]}")
[ "$STATUS" = "401" ] || fail "POST /stocks/check-availability with no token got $STATUS, expected 401"
pass "POST /stocks/check-availability with no token -> 401"

STATUS=$(DIRECT -X POST http://inventory:8000/stocks/check-availability -H "Content-Type: application/json" \
  -H "X-Internal-Token: $CUSTOMER_TOKEN" \
  -d "{\"items\": [{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 1}]}")
[ "$STATUS" = "200" ] || fail "POST /stocks/check-availability as customer got $STATUS, expected 200"
pass "POST /stocks/check-availability as customer -> 200 (identity-only, not admin-only)"

STATUS=$(DIRECT -X POST http://inventory:8000/stocks/check-availability -H "Content-Type: application/json" \
  -H "X-Internal-Token: $GUEST_TOKEN" \
  -d "{\"items\": [{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 1}]}")
[ "$STATUS" = "200" ] || fail "POST /stocks/check-availability as guest got $STATUS, expected 200"
pass "POST /stocks/check-availability as guest -> 200 (any authenticated role works)"

STATUS=$(DIRECT -X POST http://inventory:8000/stocks/check-availability -H "Content-Type: application/json" \
  -H "X-Internal-Token: $FORGED_TOKEN" \
  -d "{\"items\": [{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 1}]}")
[ "$STATUS" = "401" ] || fail "POST /stocks/check-availability with forged signature got $STATUS, expected 401"
pass "POST /stocks/check-availability with forged signature -> 401 (still needs a *valid* identity)"

STATUS=$(DIRECT -X POST http://inventory:8000/stocks/reserve -H "Content-Type: application/json" \
  -H "X-Internal-Token: $ADMIN_TOKEN" \
  -d "{\"order_id\": \"$(cat /proc/sys/kernel/random/uuid)\", \"items\": [{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 1}]}")
[ "$STATUS" = "200" ] || fail "POST /stocks/reserve as admin got $STATUS, expected 200"
pass "POST /stocks/reserve as admin -> 200"

echo
echo "All inventory-gate verification checks passed."
