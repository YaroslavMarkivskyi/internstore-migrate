#!/usr/bin/env bash
# End-to-end verification of payments-gate + internal-gate + payments-opa
# -- the sidecar chain that replaced payments' own internal-token
# verification (services/payments/src/payments/auth.py, retired). See
# scripts/verify-catalog-gate.sh and scripts/verify-security-gate.sh for
# the same idea against those services; payments is the simplest split --
# everything is admin-only except /health for the liveness/readiness
# probes (no browser-facing endpoint at all).
#
# Bypasses nginx (the external Gateway) the same way
# scripts/verify-gateway.sh's DIRECT() does: a throwaway container on the
# compose network hitting payments:8000 directly, since payments
# publishes no host port.
#
# Requires: curl, openssl, docker compose. Run after `docker compose up -d
# --build payments payments-opa payments-verify payments-gate payments-db`.
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

ADMIN_TOKEN=$(mint_token "checkout-workflow" "admin" "$SECRET")
CUSTOMER_TOKEN=$(mint_token "cust-1" "customer" "$SECRET")
FORGED_TOKEN=$(mint_token "attacker" "admin" "wrong-secret")

echo "=== 1. /health is public (no token) ==="
STATUS=$(DIRECT http://payments:8000/health)
[ "$STATUS" = "200" ] || fail "GET /health with no token got $STATUS, expected 200"
pass "GET /health with no token -> 200"

echo "=== 2. POST /charge (admin-only) ==="
STATUS=$(DIRECT -X POST http://payments:8000/charge -H "Content-Type: application/json" \
  -d "{\"order_id\": \"$(cat /proc/sys/kernel/random/uuid)\", \"amount\": 10.00, \"payment_method\": \"card\"}")
[ "$STATUS" = "401" ] || fail "POST /charge with no token got $STATUS, expected 401"
pass "POST /charge with no token -> 401"

STATUS=$(DIRECT -X POST http://payments:8000/charge -H "Content-Type: application/json" \
  -H "X-Internal-Token: $CUSTOMER_TOKEN" \
  -d "{\"order_id\": \"$(cat /proc/sys/kernel/random/uuid)\", \"amount\": 10.00, \"payment_method\": \"card\"}")
[ "$STATUS" = "403" ] || fail "POST /charge as customer got $STATUS, expected 403"
pass "POST /charge as customer -> 403 (valid token, wrong role)"

STATUS=$(DIRECT -X POST http://payments:8000/charge -H "Content-Type: application/json" \
  -H "X-Internal-Token: $FORGED_TOKEN" \
  -d "{\"order_id\": \"$(cat /proc/sys/kernel/random/uuid)\", \"amount\": 10.00, \"payment_method\": \"card\"}")
[ "$STATUS" = "401" ] || fail "POST /charge with forged signature got $STATUS, expected 401"
pass "POST /charge with forged signature -> 401 (not 403 -- no valid identity)"

STATUS=$(DIRECT -X POST http://payments:8000/charge -H "Content-Type: application/json" \
  -H "X-Internal-Token: $ADMIN_TOKEN" \
  -d "{\"order_id\": \"$(cat /proc/sys/kernel/random/uuid)\", \"amount\": 10.00, \"payment_method\": \"card\"}")
[ "$STATUS" = "201" ] || fail "POST /charge as admin got $STATUS, expected 201"
pass "POST /charge as admin -> 201"

echo "=== 3. POST /refund (same admin-only rule) ==="
STATUS=$(DIRECT -X POST http://payments:8000/refund -H "Content-Type: application/json" \
  -d "{\"payment_id\": \"$(cat /proc/sys/kernel/random/uuid)\"}")
[ "$STATUS" = "401" ] || fail "POST /refund with no token got $STATUS, expected 401"
pass "POST /refund with no token -> 401"

STATUS=$(DIRECT -X POST http://payments:8000/refund -H "Content-Type: application/json" \
  -H "X-Internal-Token: $CUSTOMER_TOKEN" \
  -d "{\"payment_id\": \"$(cat /proc/sys/kernel/random/uuid)\"}")
[ "$STATUS" = "403" ] || fail "POST /refund as customer got $STATUS, expected 403"
pass "POST /refund as customer -> 403 (valid token, wrong role)"

STATUS=$(DIRECT -X POST http://payments:8000/refund -H "Content-Type: application/json" \
  -H "X-Internal-Token: $ADMIN_TOKEN" \
  -d "{\"payment_id\": \"$(cat /proc/sys/kernel/random/uuid)\"}")
# 404 (unknown payment_id) is the real business-logic response -- what
# matters here is it's not 401/403, i.e. the gate let the admin through.
[ "$STATUS" = "404" ] || fail "POST /refund as admin got $STATUS, expected 404 (business-logic response, not a gate rejection)"
pass "POST /refund as admin -> 404 (business-logic response, gate let it through)"

echo
echo "All payments-gate verification checks passed."
