#!/usr/bin/env bash
# End-to-end verification of orders-gate + internal-gate + orders-opa --
# the sidecar chain that replaced orders' own internal-token verification
# (services/orders/src/orders/auth.py's now-removed verify_internal_token/
# require_admin/require_admin_or_assistant). See scripts/verify-catalog-gate.sh,
# verify-security-gate.sh, verify-payments-gate.sh, and
# verify-inventory-gate.sh for the same idea against those services.
#
# Orders is the HYBRID case: orders-gate only handles the coarse,
# route-level tier (public/admin/admin-or-assistant/any-authenticated) --
# it forwards X-User-Id/X-User-Role once verified, and orders' own code
# still does its own resource-ownership check for GET /orders/{id} (see
# policies/orders.rego's resource-level rules, queried directly by
# routers/orders.py). This script only exercises the gate-level tiers;
# the ownership check itself is covered by services/orders/tests/test_orders.py.
#
# Bypasses nginx (the external Gateway) the same way
# scripts/verify-gateway.sh's DIRECT() does: a throwaway container on the
# compose network hitting orders:8000 directly, since orders publishes no
# host port.
#
# Requires: curl, openssl, docker compose. Run after `docker compose up -d
# --build orders orders-opa orders-verify orders-gate orders-db kafka`.
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
ASSISTANT_TOKEN=$(mint_token "ai-assistant" "assistant" "$SECRET")
FORGED_TOKEN=$(mint_token "attacker" "admin" "wrong-secret")

echo "=== 1. /health is public (no token) ==="
STATUS=$(DIRECT http://orders:8000/health)
[ "$STATUS" = "200" ] || fail "GET /health with no token got $STATUS, expected 200"
pass "GET /health with no token -> 200"

echo "=== 2. /webhooks/stripe is public (no internal token; Stripe signature is its own auth) ==="
STATUS=$(DIRECT -X POST http://orders:8000/webhooks/stripe -H "Content-Type: application/json" -d '{}')
# 400 (missing/invalid Stripe-Signature) is the real business-logic
# response -- what matters is it's not 401, i.e. the gate let it through
# with no internal token at all.
[ "$STATUS" = "400" ] || fail "POST /webhooks/stripe with no token got $STATUS, expected 400 (business-logic response, not a gate rejection)"
pass "POST /webhooks/stripe with no token -> 400 (gate doesn't touch this route)"

echo "=== 3. cart/orders/checkout are 'any authenticated caller' ==="
STATUS=$(DIRECT http://orders:8000/cart)
[ "$STATUS" = "401" ] || fail "GET /cart with no token got $STATUS, expected 401"
pass "GET /cart with no token -> 401"

STATUS=$(DIRECT http://orders:8000/cart -H "X-Internal-Token: $FORGED_TOKEN")
[ "$STATUS" = "401" ] || fail "GET /cart with forged signature got $STATUS, expected 401"
pass "GET /cart with forged signature -> 401"

STATUS=$(DIRECT http://orders:8000/cart -H "X-Internal-Token: $CUSTOMER_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /cart as customer got $STATUS, expected 200"
pass "GET /cart as customer -> 200"

STATUS=$(DIRECT http://orders:8000/orders -H "X-Internal-Token: $CUSTOMER_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /orders as customer got $STATUS, expected 200"
pass "GET /orders as customer -> 200"

echo "=== 4. GET /admin is admin-or-assistant ==="
STATUS=$(DIRECT http://orders:8000/admin)
[ "$STATUS" = "401" ] || fail "GET /admin with no token got $STATUS, expected 401"
pass "GET /admin with no token -> 401"

STATUS=$(DIRECT http://orders:8000/admin -H "X-Internal-Token: $CUSTOMER_TOKEN")
[ "$STATUS" = "403" ] || fail "GET /admin as customer got $STATUS, expected 403"
pass "GET /admin as customer -> 403 (valid token, wrong role)"

STATUS=$(DIRECT http://orders:8000/admin -H "X-Internal-Token: $ASSISTANT_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /admin as assistant got $STATUS, expected 200"
pass "GET /admin as assistant -> 200"

STATUS=$(DIRECT http://orders:8000/admin -H "X-Internal-Token: $ADMIN_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /admin as admin got $STATUS, expected 200"
pass "GET /admin as admin -> 200"

echo "=== 5. GET /admin/{id} (and pay/ship) are admin-only, not admin-or-assistant ==="
RANDOM_ID="00000000-0000-0000-0000-000000000001"
STATUS=$(DIRECT "http://orders:8000/admin/$RANDOM_ID" -H "X-Internal-Token: $ASSISTANT_TOKEN")
[ "$STATUS" = "403" ] || fail "GET /admin/{id} as assistant got $STATUS, expected 403"
pass "GET /admin/{id} as assistant -> 403 (admin-or-assistant only applies to the list route)"

STATUS=$(DIRECT "http://orders:8000/admin/$RANDOM_ID" -H "X-Internal-Token: $ADMIN_TOKEN")
# 404 (unknown order) is the real business-logic response -- what matters
# is it's not 401/403, i.e. the gate let the admin through.
[ "$STATUS" = "404" ] || fail "GET /admin/{id} as admin got $STATUS, expected 404 (business-logic response, not a gate rejection)"
pass "GET /admin/{id} as admin -> 404 (business-logic response, gate let it through)"

echo "=== 6. /internal/checkout-workflow/* is admin-only ==="
STATUS=$(DIRECT -X POST http://orders:8000/internal/checkout-workflow/orders -H "Content-Type: application/json" \
  -H "X-Internal-Token: $CUSTOMER_TOKEN" -d '{}')
[ "$STATUS" = "403" ] || fail "POST /internal/checkout-workflow/orders as customer got $STATUS, expected 403"
pass "POST /internal/checkout-workflow/orders as customer -> 403"

STATUS=$(DIRECT -X POST http://orders:8000/internal/checkout-workflow/orders -H "Content-Type: application/json" \
  -H "X-Internal-Token: $ADMIN_TOKEN" -d '{}')
# 422 (missing required fields in this empty body) is the real
# business-logic response -- what matters is it's not 401/403.
[ "$STATUS" = "422" ] || fail "POST /internal/checkout-workflow/orders as admin got $STATUS, expected 422 (business-logic response, not a gate rejection)"
pass "POST /internal/checkout-workflow/orders as admin -> 422 (business-logic response, gate let it through)"

echo
echo "All orders-gate verification checks passed."
