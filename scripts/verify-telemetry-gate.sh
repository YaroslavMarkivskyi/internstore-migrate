#!/usr/bin/env bash
# End-to-end verification of telemetry-gate + internal-gate + telemetry-opa
# -- the sidecar chain that replaced telemetry's own internal-token
# verification (services/telemetry/src/telemetry/auth.py, deleted
# entirely -- this service never minted its own outbound token, so
# there's nothing left to keep). See scripts/verify-security-gate.sh for
# the same idea against a similarly simple path-based split; telemetry is
# even simpler: everything gated is admin-only, no role differentiation
# needed at all.
#
# Bypasses nginx (the external Gateway) the same way
# scripts/verify-gateway.sh's DIRECT() does: a throwaway container on the
# compose network hitting telemetry:8000 directly, since telemetry
# publishes no host port.
#
# Requires: curl, openssl, docker compose. Run after `docker compose up -d
# --build telemetry telemetry-opa telemetry-verify telemetry-gate
# telemetry-db kafka`.
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

echo "=== 1. /health, GET /stores, POST /measurements are all public ==="
STATUS=$(DIRECT http://telemetry:8000/health)
[ "$STATUS" = "200" ] || fail "GET /health with no token got $STATUS, expected 200"
pass "GET /health with no token -> 200"

STATUS=$(DIRECT http://telemetry:8000/stores)
[ "$STATUS" = "200" ] || fail "GET /stores with no token got $STATUS, expected 200"
pass "GET /stores with no token -> 200"

STORE_ID="00000000-0000-0000-0000-000000000001"
STATUS=$(DIRECT -X POST http://telemetry:8000/measurements -H "Content-Type: application/json" \
  -d "{\"store_id\": \"$STORE_ID\", \"temperature\": 4.0}")
[ "$STATUS" = "201" ] || fail "POST /measurements with no token got $STATUS, expected 201"
pass "POST /measurements with no token -> 201 (telemetry-simulator has no session to send)"

echo "=== 2. Every /stores/{id}/* route is admin-only ==="
STATUS=$(DIRECT "http://telemetry:8000/stores/$STORE_ID/readings")
[ "$STATUS" = "401" ] || fail "GET /stores/{id}/readings with no token got $STATUS, expected 401"
pass "GET /stores/{id}/readings with no token -> 401"

STATUS=$(DIRECT "http://telemetry:8000/stores/$STORE_ID/readings" -H "X-Internal-Token: $CUSTOMER_TOKEN")
[ "$STATUS" = "403" ] || fail "GET /stores/{id}/readings as customer got $STATUS, expected 403"
pass "GET /stores/{id}/readings as customer -> 403 (valid token, wrong role)"

STATUS=$(DIRECT "http://telemetry:8000/stores/$STORE_ID/readings" -H "X-Internal-Token: $FORGED_TOKEN")
[ "$STATUS" = "401" ] || fail "GET /stores/{id}/readings with forged signature got $STATUS, expected 401"
pass "GET /stores/{id}/readings with forged signature -> 401 (not 403 -- no valid identity)"

STATUS=$(DIRECT "http://telemetry:8000/stores/$STORE_ID/readings" -H "X-Internal-Token: $ADMIN_TOKEN")
[ "$STATUS" = "200" ] || fail "GET /stores/{id}/readings as admin got $STATUS, expected 200"
pass "GET /stores/{id}/readings as admin -> 200"

STATUS=$(DIRECT -X PATCH "http://telemetry:8000/stores/$STORE_ID" -H "Content-Type: application/json" \
  -H "X-Internal-Token: $ADMIN_TOKEN" -d '{"threshold_temp": 8}')
[ "$STATUS" = "200" ] || fail "PATCH /stores/{id} as admin got $STATUS, expected 200"
pass "PATCH /stores/{id} as admin -> 200"

STATUS=$(DIRECT "http://telemetry:8000/stores/$STORE_ID/incidents" -H "X-Internal-Token: $CUSTOMER_TOKEN")
[ "$STATUS" = "403" ] || fail "GET /stores/{id}/incidents as customer got $STATUS, expected 403"
pass "GET /stores/{id}/incidents as customer -> 403"

echo
echo "All telemetry-gate verification checks passed."
