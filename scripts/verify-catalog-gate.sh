#!/usr/bin/env bash
# End-to-end verification of catalog-gate + internal-gate + catalog-opa --
# the sidecar chain that replaced catalog's own internal-token
# verification (services/catalog/src/catalog/auth.py, retired). Mints raw
# internal (HS256) tokens directly rather than going through the real
# Gateway/Firebase flow, since this is specifically testing the internal
# boundary (catalog:8000 -> catalog-gate -> internal-gate -> catalog-opa
# -> catalog app), not the external one -- see scripts/verify-gateway.sh
# for that.
#
# Bypasses nginx (the external Gateway) the same way
# scripts/verify-gateway.sh's DIRECT() does for its own internal-token
# isolation checks: a throwaway container on the compose network hitting
# catalog:8000 directly, since catalog publishes no host port.
#
# Requires: curl, openssl, docker compose. Run after `docker compose up -d
# --build catalog catalog-opa catalog-verify catalog-gate`.
set -euo pipefail

NETWORK="internstore-migrate_default"
SECRET="dev-only-internal-secret-change-me"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

b64url() {
  openssl base64 -e -A | tr '+/' '-_' | tr -d '='
}

# HS256 JWT, signed by hand (openssl) so this script has no dependency
# beyond what's already assumed elsewhere in scripts/*.sh -- same shape
# auth-backend's real internal-token minting produces (sub, role, iss,
# iat, exp), see services/auth-backend/src/auth_backend/auth/internal_token.py.
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
FORGED_TOKEN=$(mint_token "attacker" "admin" "wrong-secret")
EXPIRED_TOKEN=$(mint_token "admin-1" "admin" "$SECRET" -300)

echo "=== 1. GET is public, no token needed ==="
STATUS=$(DIRECT http://catalog:8000/categories)
[ "$STATUS" = "200" ] || fail "GET /categories with no token got $STATUS, expected 200"
pass "GET /categories with no token -> 200"

# Short, $RANDOM-suffixed names -- Catalog's `name` schema caps at 15
# chars (max_length=15, see services/catalog/src/catalog/schemas.py) and
# repeat runs against a persistent dev DB shouldn't collide with a
# previous run's leftover row (same reasoning as scripts/verify-gateway.sh's
# PROBE_CATEGORY).
echo "=== 2. POST as admin -> 201, as customer -> 403 ==="
STATUS=$(DIRECT -X POST http://catalog:8000/categories -H "Content-Type: application/json" \
  -H "X-Internal-Token: $ADMIN_TOKEN" -d "{\"name\": \"gt-a-$RANDOM\"}")
[ "$STATUS" = "201" ] || fail "POST /categories as admin got $STATUS, expected 201"
pass "POST /categories as admin -> 201"

STATUS=$(DIRECT -X POST http://catalog:8000/categories -H "Content-Type: application/json" \
  -H "X-Internal-Token: $CUSTOMER_TOKEN" -d "{\"name\": \"gt-c-$RANDOM\"}")
[ "$STATUS" = "403" ] || fail "POST /categories as customer got $STATUS, expected 403"
pass "POST /categories as customer -> 403 (valid token, wrong role)"

echo "=== 3. POST with no / forged / expired token -> 401, not 403 ==="
STATUS=$(DIRECT -X POST http://catalog:8000/categories -H "Content-Type: application/json" -d "{\"name\": \"gt-n-$RANDOM\"}")
[ "$STATUS" = "401" ] || fail "POST /categories with no token got $STATUS, expected 401"
pass "POST /categories with no token -> 401"

STATUS=$(DIRECT -X POST http://catalog:8000/categories -H "Content-Type: application/json" \
  -H "X-Internal-Token: $FORGED_TOKEN" -d "{\"name\": \"gt-f-$RANDOM\"}")
[ "$STATUS" = "401" ] || fail "POST /categories with forged signature got $STATUS, expected 401"
pass "POST /categories with forged signature -> 401 (not 403 -- no valid identity, not just wrong role)"

STATUS=$(DIRECT -X POST http://catalog:8000/categories -H "Content-Type: application/json" \
  -H "X-Internal-Token: $EXPIRED_TOKEN" -d "{\"name\": \"gt-e-$RANDOM\"}")
[ "$STATUS" = "401" ] || fail "POST /categories with expired token got $STATUS, expected 401"
pass "POST /categories with expired token -> 401"

echo "=== 4. require_admin-shaped path (PATCH/DELETE) enforces the same way ==="
CAT_ID=$(docker run --rm --network "$NETWORK" curlimages/curl -s http://catalog:8000/categories \
  | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
[ -n "$CAT_ID" ] || fail "could not find a category id to PATCH against"

STATUS=$(DIRECT -X PATCH "http://catalog:8000/categories/$CAT_ID" -H "Content-Type: application/json" \
  -H "X-Internal-Token: $ADMIN_TOKEN" -d "{\"name\": \"gt-r-$RANDOM\"}")
[ "$STATUS" = "200" ] || fail "PATCH /categories/:id as admin got $STATUS, expected 200"
pass "PATCH /categories/:id as admin -> 200"

STATUS=$(DIRECT -X PATCH "http://catalog:8000/categories/$CAT_ID" -H "Content-Type: application/json" \
  -H "X-Internal-Token: $FORGED_TOKEN" -d "{\"name\": \"gt-x-$RANDOM\"}")
[ "$STATUS" = "401" ] || fail "PATCH /categories/:id with forged token got $STATUS, expected 401"
pass "PATCH /categories/:id with forged token -> 401"

echo
echo "All catalog-gate verification checks passed."
