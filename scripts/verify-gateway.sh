#!/usr/bin/env bash
# End-to-end verification of the nginx + auth-backend Gateway, beyond just
# "a request with a valid token returns 200". Covers:
#
#   1. Healthy path: valid Keycloak token -> nginx -> auth-backend -> echo-service
#   2. Negative scenarios: no token / corrupted signature / wrong realm / expired
#   3. Internal-token isolation: echo-service only trusts a verified internal
#      token (separate HMAC secret from the external JWT, short TTL enforced
#      downstream), never the raw external JWT or unverified headers
#   4. JWKS caching: auth-backend keeps validating already-cached keys with
#      Keycloak stopped (no synchronous per-request call to Keycloak)
#   5. WebSocket proxy: nginx forwards the Upgrade/Connection handshake and
#      still gates it with auth_request (no real chat-service backend yet,
#      so this section is skipped unless one is reachable)
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
RESPONSE=$($CURL "$GATEWAY_URL/" -H "Authorization: Bearer $TOKEN")
[ "$(echo "$RESPONSE" | jq -r .userRole)" = "customer" ] || fail "echo-service did not see userRole=customer (got: $RESPONSE)"
pass "valid token reaches echo-service via nginx + auth-backend with role=customer"

echo "=== 2. Negative scenarios ==="
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/")
[ "$STATUS" = "401" ] || fail "no token got $STATUS, expected 401"
pass "no token -> 401"

# Flip a character well inside the signature, not the very last one: base64
# encodes in 3-byte/4-char groups, and a 2048-bit RSA signature (256 bytes)
# isn't a multiple of 3, so the trailing char only carries 2 significant
# bits -- some substitutions there decode to the same byte and aren't
# actually corrupted at all, which flaked this check intermittently.
CORRUPT_POS=$((${#TOKEN} - 20))
ORIG_CHAR="${TOKEN:$CORRUPT_POS:1}"
REPLACEMENT="X"; [ "$ORIG_CHAR" = "X" ] && REPLACEMENT="Y"
CORRUPTED_TOKEN="${TOKEN:0:$CORRUPT_POS}${REPLACEMENT}${TOKEN:$((CORRUPT_POS + 1))}"
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/" -H "Authorization: Bearer $CORRUPTED_TOKEN")
[ "$STATUS" = "401" ] || fail "corrupted signature got $STATUS, expected 401"
pass "corrupted signature -> 401"

WRONG_REALM_TOKEN=$(admin_token)
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/" -H "Authorization: Bearer $WRONG_REALM_TOKEN")
[ "$STATUS" = "401" ] || fail "token from wrong realm got $STATUS, expected 401"
pass "token from wrong realm (iss mismatch) -> 401"

ADMIN_TOKEN=$(admin_token)
curl -sf -X PUT "$KC_URL/admin/realms/$REALM" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d '{"accessTokenLifespan": 3}' >/dev/null
SHORT_TOKEN=$(login "customer@example.com" "Customer123")
sleep 5
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/" -H "Authorization: Bearer $SHORT_TOKEN")
curl -sf -X PUT "$KC_URL/admin/realms/$REALM" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d '{"accessTokenLifespan": 300}' >/dev/null
[ "$STATUS" = "401" ] || fail "expired token got $STATUS, expected 401"
pass "expired token -> 401 (realm lifespan restored)"

echo "=== 3. Internal token isolation (bypassing nginx, hitting echo-service directly) ==="
DIRECT() { docker run --rm --network internstore-migrate_default curlimages/curl -s -o /dev/null -w "%{http_code}" "$@"; }

STATUS=$(DIRECT http://echo-service:4000/ -H "X-User-Id: attacker" -H "X-User-Role: admin" -H "X-Internal-Token: forged-garbage")
[ "$STATUS" = "401" ] || fail "echo-service accepted a forged internal token (got $STATUS) -- it must validate the token itself, not trust headers"
pass "forged internal token rejected by echo-service directly (headers alone are not trusted)"

STATUS=$(DIRECT http://echo-service:4000/)
[ "$STATUS" = "401" ] || fail "echo-service accepted a request with no internal token (got $STATUS)"
pass "missing internal token rejected by echo-service directly"

INTERNAL=$(curl -sf "$AUTH_BACKEND_URL/me" -H "Authorization: Bearer $TOKEN" | jq -r .internalToken)
[ "$INTERNAL" != "null" ] && [ -n "$INTERNAL" ] || fail "auth-backend did not mint an internal token"
echo "$INTERNAL" | cut -d. -f1 | base64 -d 2>/dev/null | grep -q '"HS256"' \
  || fail "internal token is not HS256 (expected a distinct HMAC signing scheme from the external RS256 JWT)"
pass "internal token uses HS256 with a separate secret, not the external token's RS256/Keycloak key"

echo "waiting 65s for the internal token's 60s TTL to lapse..."
sleep 65
STATUS=$(DIRECT http://echo-service:4000/ -H "X-Internal-Token: $INTERNAL")
[ "$STATUS" = "401" ] || fail "expired internal token still accepted by echo-service (got $STATUS)"
pass "internal token TTL (~60s) is enforced downstream, independent of the external token's lifetime"

echo "=== 4. JWKS caching survives Keycloak being unreachable ==="
TOKEN=$(login "customer@example.com" "Customer123")
docker compose stop keycloak >/dev/null
STATUS=$($CURL -o /dev/null -w "%{http_code}" "$GATEWAY_URL/" -H "Authorization: Bearer $TOKEN")
docker compose start keycloak >/dev/null
[ "$STATUS" = "200" ] || fail "verification failed with Keycloak stopped (got $STATUS) -- JWKS should be cached in-process"
pass "auth-backend validates already-cached JWKS keys with Keycloak stopped (no synchronous per-request call)"

echo "waiting for keycloak to report healthy again..."
for _ in $(seq 1 20); do
  [ "$(docker inspect --format='{{.State.Health.Status}}' internstore-migrate-keycloak-1 2>/dev/null)" = "healthy" ] && break
  sleep 3
done

echo "=== 5. WebSocket proxy (auth_request + Upgrade header forwarding) ==="
TOKEN=$(login "customer@example.com" "Customer123")
STATUS=$($CURL -o /dev/null -w "%{http_code}" -N "$GATEWAY_URL/ws/echo" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==")
if [ "$STATUS" = "502" ]; then
  echo "SKIP: /ws/ has no chat-service backend yet (502 is expected until Chat exists); auth gating still verified below"
  UNAUTH_STATUS=$($CURL -o /dev/null -w "%{http_code}" -N "$GATEWAY_URL/ws/echo" \
    -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" \
    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==")
  [ "$UNAUTH_STATUS" = "401" ] || fail "/ws/ without a token got $UNAUTH_STATUS, expected 401"
  pass "/ws/ still enforces auth_request even with no backend behind it"
elif [ "$STATUS" = "101" ]; then
  pass "/ws/ completes the WebSocket handshake through nginx"
else
  fail "/ws/ returned unexpected status $STATUS"
fi

echo
echo "All gateway verification checks passed."
