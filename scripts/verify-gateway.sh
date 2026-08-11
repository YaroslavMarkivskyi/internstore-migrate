#!/usr/bin/env bash
# K8s counterpart: scripts/k8s/verify-gateway.sh (STR-145). If you fix a
# bug in this script, check whether the same bug exists there too -- see
# STR-151, which found fixes made in one copy that were never ported to
# the other.
#
# End-to-end verification of the nginx + auth-backend Gateway, beyond just
# "a request with a valid token returns 200". Covers:
#
#   1. Healthy path: valid Keycloak token -> nginx -> auth-backend -> Catalog,
#      with X-User-Role actually enforced downstream (customer 403s on an
#      admin-only write, admin 201s)
#   2. Negative scenarios: no token / corrupted signature / wrong realm / expired
#   3. Internal-token isolation: Catalog only trusts a verified internal
#      token (separate HMAC secret from the external JWT, short TTL enforced
#      downstream), never the raw external JWT or unverified headers
#   4. Keycloak-unreachable behavior: auth-backend's AUTH-05 revocation
#      check fails closed (401) on a not-yet-introspected token when
#      Keycloak is stopped, rather than silently trusting it
#   5. WebSocket proxy: nginx still gates /ws/ with auth_request for an
#      unauthenticated handshake attempt (full authenticated WS round-trip
#      is covered by test-chat-saga.sh, which owns a real chat room)
#
# Requires: curl, jq, docker compose. Run after `docker compose up -d`.
# Mutates the realm's accessTokenLifespan temporarily (restored on exit) and
# briefly stops/restarts the keycloak container — expect ~15-20s runtime.
set -euo pipefail

KC_URL="http://localhost:8081"
GATEWAY_URL="https://localhost:8443"
AUTH_BACKEND_URL="http://localhost:3000"
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

admin_token() {
  curl -sf -X POST "$KC_URL/realms/master/protocol/openid-connect/token" \
    -d "client_id=admin-cli" -d "grant_type=password" -d "username=admin" -d "password=admin" \
    | jq -r .access_token
}

echo "=== 1. Healthy path ==="
TOKEN=$(login "customer@example.com" "Customer123")
[ "$TOKEN" != "null" ] || fail "customer login did not return an access token"
KC_ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$KC_ADMIN_TOKEN" != "null" ] || fail "admin login did not return an access token"

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
  -H "Authorization: Bearer $KC_ADMIN_TOKEN" -H "Content-Type: application/json" \
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

# Flip a character well inside the signature, not the very last one: base64
# encodes in 3-byte/4-char groups, and a 2048-bit RSA signature (256 bytes)
# isn't a multiple of 3, so the trailing char only carries 2 significant
# bits -- some substitutions there decode to the same byte and aren't
# actually corrupted at all, which flaked this check intermittently.
CORRUPT_POS=$((${#TOKEN} - 20))
ORIG_CHAR="${TOKEN:$CORRUPT_POS:1}"
REPLACEMENT="X"; [ "$ORIG_CHAR" = "X" ] && REPLACEMENT="Y"
CORRUPTED_TOKEN="${TOKEN:0:$CORRUPT_POS}${REPLACEMENT}${TOKEN:$((CORRUPT_POS + 1))}"
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/api/catalog/categories" -H "Authorization: Bearer $CORRUPTED_TOKEN")
[ "$STATUS" = "401" ] || fail "corrupted signature got $STATUS, expected 401"
pass "corrupted signature -> 401"

WRONG_REALM_TOKEN=$(admin_token)
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/api/catalog/categories" -H "Authorization: Bearer $WRONG_REALM_TOKEN")
[ "$STATUS" = "401" ] || fail "token from wrong realm got $STATUS, expected 401"
pass "token from wrong realm (iss mismatch) -> 401"

ADMIN_TOKEN=$(admin_token)
curl -sf -X PUT "$KC_URL/admin/realms/$REALM" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d '{"accessTokenLifespan": 3}' >/dev/null
SHORT_TOKEN=$(login "customer@example.com" "Customer123")
sleep 5
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/api/catalog/categories" -H "Authorization: Bearer $SHORT_TOKEN")
curl -sf -X PUT "$KC_URL/admin/realms/$REALM" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d '{"accessTokenLifespan": 300}' >/dev/null
[ "$STATUS" = "401" ] || fail "expired token got $STATUS, expected 401"
pass "expired token -> 401 (realm lifespan restored)"

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
  || fail "internal token is not HS256 (expected a distinct HMAC signing scheme from the external RS256 JWT)"
pass "internal token uses HS256 with a separate secret, not the external token's RS256/Keycloak key"

echo "waiting 65s for the internal token's 60s TTL to lapse..."
sleep 65
STATUS=$(DIRECT http://catalog:8000/categories -H "X-Internal-Token: $INTERNAL")
[ "$STATUS" = "401" ] || fail "expired internal token still accepted by Catalog (got $STATUS)"
pass "internal token TTL (~60s) is enforced downstream, independent of the external token's lifetime"

echo "=== 4. Keycloak-unreachable behavior ==="
# STR-151: this used to assert 200 ("JWKS cached in-process, no synchronous
# per-request call to Keycloak"), but auth-backend's RevocationChecker
# (AUTH-05, auth/revocation.py) does its own live token introspection call
# to Keycloak per *token* (30s TTL cache, keyed by token hash) independent
# of JWKS caching, and deliberately fails closed (treats the token as
# revoked -> 401) when Keycloak is unreachable and that token's
# introspection isn't already cached -- "an unreachable or erroring
# Keycloak must not silently fall back to trusting the token" per that
# file's own comment. A fresh token minted right before Keycloak goes down
# was never introspected, so it 401s, correctly, by design. AUTH-05 was
# apparently added after this assertion was written. Found already fixed
# in scripts/k8s/verify-gateway.sh (STR-145); ported back here.
TOKEN=$(login "customer@example.com" "Customer123")
docker compose stop keycloak >/dev/null
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/api/catalog/categories" -H "Authorization: Bearer $TOKEN")
docker compose start keycloak >/dev/null
[ "$STATUS" = "401" ] || fail "verification with Keycloak stopped got $STATUS, expected 401 (AUTH-05 fail-closed revocation check on an uncached token)"
pass "auth-backend fails closed (401) on a not-yet-introspected token with Keycloak unreachable (AUTH-05) -- correct secure-by-default behavior, not a JWKS-caching gap"

echo "waiting for keycloak to report healthy again..."
for _ in $(seq 1 20); do
  [ "$(docker inspect --format='{{.State.Health.Status}}' internstore-migrate-keycloak-1 2>/dev/null)" = "healthy" ] && break
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
