#!/usr/bin/env bash
# End-to-end verification of security-gate + internal-gate + security-opa
# -- the sidecar chain that replaced security's own internal-token
# verification (services/security/src/security/auth.py, retired). See
# scripts/verify-catalog-gate.sh for the same idea against catalog; this
# is security's path-based split (not method-based -- /auth/* is always
# public, /users, /visit-log, /warehouses are always admin-only,
# including their own GET routes).
#
# Bypasses nginx (the external Gateway) the same way
# scripts/verify-gateway.sh's DIRECT() does: a throwaway container on the
# compose network hitting security:8000 directly, since security
# publishes no host port.
#
# Requires: curl, openssl, docker compose. Run after `docker compose up -d
# --build security security-opa security-verify security-gate`.
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
FORGED_TOKEN=$(mint_token "attacker" "admin" "wrong-secret")

echo "=== 1. /health is public (no token) ==="
STATUS=$(DIRECT http://security:8000/health)
[ "$STATUS" = "200" ] || fail "GET /health with no token got $STATUS, expected 200"
pass "GET /health with no token -> 200"

echo "=== 2. /auth/* (hardware simulator) is public regardless of method ==="
STATUS=$(DIRECT -X POST http://security:8000/auth/fingerprint -H "Content-Type: application/json" \
  -d '{"warehouse_id": "00000000-0000-0000-0000-000000000000", "fingerprint_template": "smoke-test"}')
# 200 (denied, unknown credential) is the real business-logic response --
# what matters here is it's not 401/403, i.e. the gate let it through
# with no token at all.
[ "$STATUS" = "200" ] || fail "POST /auth/fingerprint with no token got $STATUS, expected 200 (business-logic response, not a gate rejection)"
pass "POST /auth/fingerprint with no token -> 200 (gate doesn't touch /auth/*)"

echo "=== 3. GET /users (admin-only, including its own GET) ==="
STATUS=$(DIRECT http://security:8000/users)
[ "$STATUS" = "401" ] || fail "GET /users with no token got $STATUS, expected 401"
pass "GET /users with no token -> 401"

STATUS=$(DIRECT http://security:8000/users -H "X-Internal-Token: $CUSTOMER_TOKEN")
[ "$STATUS" = "403" ] || fail "GET /users as customer got $STATUS, expected 403"
pass "GET /users as customer -> 403 (valid token, wrong role)"

STATUS=$(DIRECT http://security:8000/users -H "X-Internal-Token: $FORGED_TOKEN")
[ "$STATUS" = "401" ] || fail "GET /users with forged signature got $STATUS, expected 401"
pass "GET /users with forged signature -> 401 (not 403 -- no valid identity)"

STATUS=$(DIRECT http://security:8000/users -H "X-Internal-Token: $ADMIN_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /users as admin got $STATUS, expected 200"
pass "GET /users as admin -> 200"

echo "=== 4. GET /visit-log and /warehouses (same admin-only-including-GET rule) ==="
STATUS=$(DIRECT http://security:8000/visit-log)
[ "$STATUS" = "401" ] || fail "GET /visit-log with no token got $STATUS, expected 401"
pass "GET /visit-log with no token -> 401"

STATUS=$(DIRECT http://security:8000/visit-log -H "X-Internal-Token: $ADMIN_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /visit-log as admin got $STATUS, expected 200"
pass "GET /visit-log as admin -> 200"

STATUS=$(DIRECT http://security:8000/warehouses)
[ "$STATUS" = "401" ] || fail "GET /warehouses with no token got $STATUS, expected 401"
pass "GET /warehouses with no token -> 401"

STATUS=$(DIRECT http://security:8000/warehouses -H "X-Internal-Token: $ADMIN_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /warehouses as admin got $STATUS, expected 200"
pass "GET /warehouses as admin -> 200"

echo
echo "All security-gate verification checks passed."
