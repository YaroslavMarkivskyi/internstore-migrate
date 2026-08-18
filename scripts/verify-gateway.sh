#!/usr/bin/env bash
# K8s counterpart: scripts/k8s/verify-gateway.sh (STR-145). If you fix a
# bug in this script, check whether the same bug exists there too -- see
# STR-151, which found fixes made in one copy that were never ported to
# the other.
#
# End-to-end verification of the nginx + auth-backend Gateway, beyond just
# "a request with a valid token returns 200". Covers:
#
#   1. Healthy path: valid Firebase token -> nginx -> auth-backend -> Catalog,
#      with X-User-Role actually enforced downstream (customer 403s on an
#      admin-only write, admin 201s)
#   2. Negative scenarios: no token / corrupted token / wrong Firebase project
#   3. Internal-token isolation: Catalog only trusts a verified internal
#      token (separate HMAC secret from the external token, short TTL
#      enforced downstream), never the raw external token or unverified
#      headers
#   4. Firebase-unreachable behavior: auth-backend's check_revoked=True
#      revocation check (STR-181/STR-192, replaces AUTH-05's old Keycloak
#      introspection) fails closed (401) with the Firebase emulator
#      stopped, rather than silently trusting the token
#   5. WebSocket proxy: nginx still gates /ws/ with auth_request for an
#      unauthenticated handshake attempt (full authenticated WS round-trip
#      is covered by test-chat-saga.sh, which owns a real chat room)
#
# Requires: curl, jq, docker compose. Run after `docker compose up -d`.
# Briefly stops/restarts the firebase-emulator container -- expect ~15-20s
# runtime.
#
# STR-192: the "expired token" negative scenario this script used to run
# under Keycloak is gone, not just translated -- verified directly (not
# assumed) that firebase_admin's verify_id_token() does NOT reject an
# expired *emulator*-issued token; the emulator's unsigned (alg: none)
# tokens skip exp/iat validation that real Firebase enforces. See
# firebase/README.md's "Known gap" section. Real Firebase in the GCP
# overlay is not affected -- this is local-dev-only, same category as the
# other gaps documented there.
set -euo pipefail

FIREBASE_AUTH_EMULATOR_URL="http://localhost:9099"
GATEWAY_URL="https://localhost:8443"
AUTH_BACKEND_URL="http://localhost:3000"
CURL="curl -sk"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

login() {
  curl -sf -X POST "$FIREBASE_AUTH_EMULATOR_URL/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$1\",\"password\":\"$2\",\"returnSecureToken\":true}" | jq -r .idToken
}

# Rewrites one claim in an unsigned emulator ID token (alg: none, so there's
# no real signature to preserve/break) -- used below to build negative-test
# tokens (corrupted payload, wrong Firebase project) without needing a
# second Firebase project or an admin API to mint them.
tamper_claim() {
  local token="$1" filter="$2" header body sig
  header=$(echo "$token" | cut -d. -f1)
  sig=$(echo "$token" | cut -d. -f3)
  body=$(echo "$token" | cut -d. -f2 | base64 -d 2>/dev/null | jq -c "$filter" | base64 -w0 | tr -d '=' | tr '+/' '-_')
  echo "${header}.${body}.${sig}"
}

echo "=== 1. Healthy path ==="
TOKEN=$(login "customer@example.com" "Customer123")
[ "$TOKEN" != "null" ] || fail "customer login did not return an ID token"
FB_ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$FB_ADMIN_TOKEN" != "null" ] || fail "admin login did not return an ID token"

# A random-suffixed category name so repeat runs against a persistent dev DB
# don't collide with a previous run's leftover row.
#
# STR-151: shortened from "gw-probe-$RANDOM" (already 13-14 chars) -- the
# "-guest" suffix used below pushes it past Catalog's `name` schema limit
# (max_length=15), so that assertion 422s instead of 403ing. Found already
# fixed in scripts/k8s/verify-gateway.sh (STR-145); ported back here.
PROBE_CATEGORY="gw-$RANDOM"

STATUS=$($CURL -o /dev/null -w "%{http_code}" -X POST "$GATEWAY_URL/api/catalog/categories" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\": \"$PROBE_CATEGORY\"}")
[ "$STATUS" = "403" ] || fail "customer token reached Catalog's admin-only endpoint (got $STATUS, expected 403) -- X-User-Role did not propagate correctly"
pass "customer token reaches Catalog via nginx + auth-backend with role=customer (rejected by Catalog's own admin check)"

STATUS=$($CURL -o /dev/null -w "%{http_code}" -X POST "$GATEWAY_URL/api/catalog/categories" \
  -H "Authorization: Bearer $FB_ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\": \"$PROBE_CATEGORY\"}")
[ "$STATUS" = "201" ] || fail "admin token could not create a category through the gateway (got $STATUS, expected 201)"
pass "admin token reaches Catalog via nginx + auth-backend with role=admin"

echo "=== 2. Negative scenarios ==="
# Catalog browsing is deliberately guest-allowed (anonymous visitors can
# view products/categories and check out — see auth-backend's
# GUEST_ALLOWED_PATH_PREFIXES) — a no-token GET here mints a guest session
# and succeeds, it does not 401.
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/api/catalog/categories")
[ "$STATUS" = "200" ] || fail "anonymous catalog browsing got $STATUS, expected 200 (guest-allowed)"
pass "no token on guest-allowed /api/catalog -> 200 (anonymous browsing)"

# A guest token is still just a guest: Catalog's own require_admin still
# 403s a guest attempting an admin-only write, same as the customer-token
# assertion above.
STATUS=$($CURL -o /dev/null -w "%{http_code}" -X POST "$GATEWAY_URL/api/catalog/categories" \
  -H "Content-Type: application/json" -d "{\"name\": \"$PROBE_CATEGORY-guest\"}")
[ "$STATUS" = "403" ] || fail "no-token write to Catalog's admin-only endpoint got $STATUS, expected 403 (guest role, not admin)"
pass "no token on Catalog's admin-only write -> 403 (guest role reaches Catalog but is rejected)"

# Inventory is NOT on the guest allowlist -- unlike Catalog, a no-token
# request here must still 401 at the Gateway, never reaching Inventory.
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/api/inventory/stocks")
[ "$STATUS" = "401" ] || fail "no token on non-guest-allowed /api/inventory got $STATUS, expected 401"
pass "no token -> 401 (non-guest-allowed service)"

# Corrupt a byte in the token's payload segment. Firebase emulator tokens
# are unsigned (alg: none, empty third segment) -- there's no real
# signature to flip, unlike a real RS256 token -- but a corrupted payload
# still fails base64/JSON parsing on decode. Verified directly against
# firebase_admin.auth.verify_id_token(): raises InvalidIdTokenError
# ("Can't parse segment...").
PAYLOAD_SEG=$(echo "$TOKEN" | cut -d. -f2)
CORRUPT_POS=$((${#PAYLOAD_SEG} / 2))
ORIG_CHAR="${PAYLOAD_SEG:$CORRUPT_POS:1}"
REPLACEMENT="X"; [ "$ORIG_CHAR" = "X" ] && REPLACEMENT="Y"
CORRUPTED_PAYLOAD="${PAYLOAD_SEG:0:$CORRUPT_POS}${REPLACEMENT}${PAYLOAD_SEG:$((CORRUPT_POS + 1))}"
CORRUPTED_TOKEN="$(echo "$TOKEN" | cut -d. -f1).${CORRUPTED_PAYLOAD}.$(echo "$TOKEN" | cut -d. -f3)"
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/api/catalog/categories" -H "Authorization: Bearer $CORRUPTED_TOKEN")
[ "$STATUS" = "401" ] || fail "corrupted token got $STATUS, expected 401"
pass "corrupted token -> 401"

# A token issued for the wrong Firebase project (aud mismatch) -- the
# closest Firebase equivalent to Keycloak's "wrong realm" test. There's no
# REST-only way to mint a token for a second project against a
# single-project emulator instance, so this rewrites the `aud`/`iss`
# claims directly (same "no real signature to preserve" reasoning as
# above) -- verified directly: verify_id_token() rejects with
# InvalidIdTokenError ("incorrect aud claim").
WRONG_AUD_TOKEN=$(tamper_claim "$TOKEN" '.aud = "some-other-project" | .iss = "https://securetoken.google.com/some-other-project"')
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/api/catalog/categories" -H "Authorization: Bearer $WRONG_AUD_TOKEN")
[ "$STATUS" = "401" ] || fail "token for the wrong Firebase project got $STATUS, expected 401"
pass "token for the wrong Firebase project (aud mismatch) -> 401"

echo "=== 3. Internal token isolation (bypassing nginx, hitting Catalog directly) ==="
DIRECT() {
  docker run --rm --network internstore-migrate_default curlimages/curl -s -o /dev/null -w "%{http_code}" \
    -X POST -H "Content-Type: application/json" -d "{\"name\": \"direct-probe-$RANDOM\"}" "$@"
}

STATUS=$(DIRECT http://catalog:8000/categories -H "X-User-Id: attacker" -H "X-User-Role: admin" -H "X-Internal-Token: forged-garbage")
[ "$STATUS" = "401" ] || fail "Catalog accepted a forged internal token (got $STATUS) -- it must validate the token itself, not trust headers"
pass "forged internal token rejected by Catalog directly (headers alone are not trusted)"

STATUS=$(DIRECT http://catalog:8000/categories)
[ "$STATUS" = "401" ] || fail "Catalog accepted a request with no internal token (got $STATUS)"
pass "missing internal token rejected by Catalog directly"

INTERNAL=$(curl -sf "$AUTH_BACKEND_URL/me" -H "Authorization: Bearer $TOKEN" | jq -r .internalToken)
[ "$INTERNAL" != "null" ] && [ -n "$INTERNAL" ] || fail "auth-backend did not mint an internal token"
echo "$INTERNAL" | cut -d. -f1 | base64 -d 2>/dev/null | grep -q '"HS256"' \
  || fail "internal token is not HS256 (expected a distinct HMAC signing scheme from the external token)"
pass "internal token uses HS256 with a separate secret, not the external Firebase token's own signing"

echo "waiting 65s for the internal token's 60s TTL to lapse..."
sleep 65
STATUS=$(DIRECT http://catalog:8000/categories -H "X-Internal-Token: $INTERNAL")
[ "$STATUS" = "401" ] || fail "expired internal token still accepted by Catalog (got $STATUS)"
pass "internal token TTL (~60s) is enforced downstream, independent of the external token's lifetime"

echo "=== 4. Firebase-unreachable behavior ==="
# STR-192: this used to stop/restart the keycloak container and assert
# auth-backend's separate RevocationChecker (auth/revocation.py,
# retired) failed closed on an uncached token. STR-181 folded revocation
# into ExternalTokenVerifier.verify() itself via check_revoked=True --
# there's no separate introspection cache anymore, so *every* token
# (fresh or not) hits this check, and Firebase Admin SDK's own
# get_user() call inside it fails closed by construction: a connection
# error there propagates as an exception rather than being swallowed. See
# services/auth-backend/src/auth_backend/auth/external_token.py.
#
# Stopping (not pausing) firebase-emulator matches Keycloak's own
# stop/start here and is deliberate: the emulator's user store is
# in-memory only (no --export-on-exit configured, see firebase/README.md)
# so a `pause` (freezes the process, verified to make auth-backend's own
# call hang instead of fail fast) would work too but a `stop` more
# faithfully reproduces "the auth provider is actually down", and nothing
# later in this script depends on the seeded users still existing
# afterward.
TOKEN=$(login "customer@example.com" "Customer123")
docker compose stop firebase-emulator >/dev/null
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/api/catalog/categories" -H "Authorization: Bearer $TOKEN")
docker compose start firebase-emulator >/dev/null
[ "$STATUS" = "401" ] || fail "verification with Firebase emulator stopped got $STATUS, expected 401 (fail-closed revocation check)"
pass "auth-backend fails closed (401) with the Firebase emulator unreachable -- correct secure-by-default behavior"

echo "waiting for firebase-emulator to report healthy again..."
for _ in $(seq 1 20); do
  [ "$(docker inspect --format='{{.State.Health.Status}}' internstore-migrate-firebase-emulator-1 2>/dev/null)" = "healthy" ] && break
  sleep 3
done

echo "=== 5. WebSocket proxy (auth_request still gates /ws/ with no token) ==="
# Deliberately NOT /ws/room/... -- that prefix is guest-allowed (Chat's
# guest connect path, see GUEST_ALLOWED_PATH_PREFIXES), so a request with no
# Authorization there correctly gets a 200 + guest token, not a 401. Any
# other path under /ws/ still goes through the same auth_request gate but
# isn't guest-allowed, so it isolates the "auth_request still runs on this
# location" check from the guest-fallback behavior.
STATUS=$($CURL -o /dev/null -w "%{http_code}" -N "$GATEWAY_URL/ws/probe" \
  -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==")
[ "$STATUS" = "401" ] || fail "/ws/ without a token got $STATUS, expected 401"
pass "/ws/ enforces auth_request on an unauthenticated handshake outside the guest allowlist (see test-chat-saga.sh for an authenticated round-trip)"

echo
echo "All gateway verification checks passed."
