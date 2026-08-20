#!/usr/bin/env bash
# Exercises AUTH-02, AUTH-03, AUTH-04, AUTH-05 against a running docker-compose
# stack (Firebase Auth emulator on :9099, Gateway on :3000), for both the
# customer and admin seed users from scripts/seed-firebase-users.py.
#
# AUTH-01 (self-registration) is a browser form flow, not scripted here --
# there's no Firebase-hosted equivalent either, self-registration would be the
# frontend's own Firebase JS SDK sign-up call, out of scope for this repo
# per STR-181/STR-192).
#
# Requires: curl, jq, uv (for scripts/firebase-admin-cli.py -- AUTH-04/05
# below use Admin SDK operations with no REST equivalent reachable from
# curl/jq alone, unlike login which uses the Identity Toolkit REST API
# directly). Run after `docker compose up -d` and
# `uv run scripts/seed-firebase-users.py`.
set -euo pipefail

FIREBASE_AUTH_EMULATOR_URL="http://localhost:9099"
GATEWAY_URL="http://localhost:3000"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

login() {
  curl -sf -X POST "$FIREBASE_AUTH_EMULATOR_URL/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$1\",\"password\":\"$2\",\"returnSecureToken\":true}"
}

for user in "customer@example.com:Customer123:customer" "admin@example.com:Admin123456:admin"; do
  IFS=':' read -r EMAIL PASSWORD EXPECTED_ROLE <<< "$user"
  echo "--- Testing $EMAIL (expected role: $EXPECTED_ROLE) ---"

  # AUTH-02: login
  TOKENS=$(login "$EMAIL" "$PASSWORD") || fail "$EMAIL login"
  ID_TOKEN=$(echo "$TOKENS" | jq -r .idToken)
  UID_VAL=$(echo "$TOKENS" | jq -r .localId)
  [ "$ID_TOKEN" != "null" ] || fail "$EMAIL did not receive an ID token"
  ROLE_IN_TOKEN=$(echo "$ID_TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | jq -r '.role' || true)
  [ "$ROLE_IN_TOKEN" = "$EXPECTED_ROLE" ] || fail "$EMAIL token role mismatch (got '$ROLE_IN_TOKEN')"
  pass "$EMAIL login (AUTH-02)"

  # AUTH-03: gateway validates external Firebase token and mints an
  # internal token (firebase_admin.auth.verify_id_token())
  ME=$(curl -sf "$GATEWAY_URL/me" -H "Authorization: Bearer $ID_TOKEN") || fail "$EMAIL gateway /me"
  GW_ROLE=$(echo "$ME" | jq -r .role)
  INTERNAL_TOKEN=$(echo "$ME" | jq -r .internalToken)
  [ "$GW_ROLE" = "$EXPECTED_ROLE" ] || fail "$EMAIL gateway role mismatch"
  [ "$INTERNAL_TOKEN" != "null" ] || fail "$EMAIL did not receive internal token"
  pass "$EMAIL gateway Firebase token validation + internal token mint (AUTH-03)"

  # AUTH-04: change password. Uses the Identity Toolkit REST API's own
  # accounts:update (idToken + new password) -- genuinely self-service.
  NEW_PASSWORD="${PASSWORD}New1"
  curl -sf -X POST "$FIREBASE_AUTH_EMULATOR_URL/identitytoolkit.googleapis.com/v1/accounts:update?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"idToken\":\"$ID_TOKEN\",\"password\":\"$NEW_PASSWORD\",\"returnSecureToken\":false}" >/dev/null \
    || fail "$EMAIL password change"

  login "$EMAIL" "$NEW_PASSWORD" >/dev/null || fail "$EMAIL login with new password"
  pass "$EMAIL new password works (AUTH-04)"
  if login "$EMAIL" "$PASSWORD" >/dev/null 2>&1; then
    fail "$EMAIL old password still works after change"
  fi
  pass "$EMAIL old password rejected (AUTH-04)"

  # AUTH-05: revocation. Firebase's client REST API has no logout-revokes
  # endpoint -- revoke_refresh_tokens is Admin SDK-only, see
  # scripts/firebase-admin-cli.py. This is the direct, real-HTTP-path
  # version of what STR-181 verified manually: revoke a user's tokens,
  # confirm /auth/verify's check_revoked=True rejects their still
  # unexpired ID token.
  FRESH_TOKENS=$(login "$EMAIL" "$NEW_PASSWORD")
  FRESH_ID_TOKEN=$(echo "$FRESH_TOKENS" | jq -r .idToken)
  STATUS_BEFORE=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/auth/verify" -H "Authorization: Bearer $FRESH_ID_TOKEN")
  [ "$STATUS_BEFORE" = "200" ] || fail "$EMAIL fresh token rejected before revocation (got $STATUS_BEFORE)"

  # check_revoked's comparison (external_token.py) is `iat*1000 <
  # tokens_valid_after_timestamp` -- iat is second-granularity, so
  # revoking within the same wall-clock second as login doesn't reliably
  # register as "after" the token. Verified directly: without this sleep,
  # the revoked-token check below flakes ~200 instead of 401. A short gap
  # avoids the race; this isn't emulator-specific, the same granularity
  # applies against real Firebase too.
  sleep 2
  uv run "$(dirname "${BASH_SOURCE[0]}")/firebase-admin-cli.py" revoke-refresh-tokens "$UID_VAL" >/dev/null \
    || fail "$EMAIL revoke-refresh-tokens"

  STATUS_AFTER=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/auth/verify" -H "Authorization: Bearer $FRESH_ID_TOKEN")
  [ "$STATUS_AFTER" = "401" ] || fail "$EMAIL revoked token still accepted (got $STATUS_AFTER, expected 401)"
  pass "$EMAIL revoked token rejected by /auth/verify (AUTH-05, check_revoked=True)"

  # Restore original password so the script is re-runnable.
  curl -sf -X POST "$FIREBASE_AUTH_EMULATOR_URL/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$NEW_PASSWORD\",\"returnSecureToken\":true}" \
    | jq -r .idToken > /tmp/_auth_flows_restore_token
  curl -sf -X POST "$FIREBASE_AUTH_EMULATOR_URL/identitytoolkit.googleapis.com/v1/accounts:update?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"idToken\":\"$(cat /tmp/_auth_flows_restore_token)\",\"password\":\"$PASSWORD\",\"returnSecureToken\":false}" >/dev/null \
    || fail "$EMAIL password restore"
  rm -f /tmp/_auth_flows_restore_token
done

echo "--- Testing guest session fallback (/auth/verify) ---"

# No Authorization header, X-Original-URI outside the guest allowlist -> 401.
# (This script talks to auth-backend directly, bypassing nginx, so it must
# synthesize the X-Original-URI header nginx would normally set.)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/auth/verify" \
  -H "X-Original-URI: /api/orders/orders")
[ "$STATUS" = "401" ] || fail "guest fallback allowed on a non-allowlisted path (got $STATUS)"
pass "guest fallback rejected outside the allowlist"

# No Authorization header, allowlisted path -> 200 + Set-Cookie + a fresh guest identity.
RESPONSE_HEADERS=$(curl -s -D - -o /dev/null "$GATEWAY_URL/auth/verify" \
  -H "X-Original-URI: /api/orders/cart")
echo "$RESPONSE_HEADERS" | grep -qi '^HTTP/.* 200' || fail "guest fallback did not return 200"
GUEST_COOKIE=$(echo "$RESPONSE_HEADERS" | grep -i '^set-cookie:' | sed -E 's/^[Ss]et-[Cc]ookie: ([^;]+);.*/\1/' | tr -d '\r')
[ -n "$GUEST_COOKIE" ] || fail "guest fallback did not set a cookie"
GUEST_ID=$(echo "$RESPONSE_HEADERS" | grep -i '^x-user-id:' | cut -d' ' -f2 | tr -d '\r')
GUEST_ROLE=$(echo "$RESPONSE_HEADERS" | grep -i '^x-user-role:' | cut -d' ' -f2 | tr -d '\r')
[ "$GUEST_ROLE" = "guest" ] || fail "guest fallback role mismatch (got '$GUEST_ROLE')"
pass "guest fallback issues a cookie + role=guest internal token"

# Same cookie, second request -> same guest identity reused, no new cookie.
RESPONSE_HEADERS_2=$(curl -s -D - -o /dev/null "$GATEWAY_URL/auth/verify" \
  -H "X-Original-URI: /api/orders/checkout" -H "Cookie: $GUEST_COOKIE")
GUEST_ID_2=$(echo "$RESPONSE_HEADERS_2" | grep -i '^x-user-id:' | cut -d' ' -f2 | tr -d '\r')
[ "$GUEST_ID_2" = "$GUEST_ID" ] || fail "guest identity not reused across requests with the same cookie"
pass "guest identity reused via cookie across requests (AUTH guest fallback)"

echo "All AUTH-02..05 + guest fallback checks passed."
