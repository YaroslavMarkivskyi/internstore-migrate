#!/usr/bin/env bash
# Exercises AUTH-02, AUTH-03, AUTH-04, AUTH-05 against a running docker-compose
# stack (Keycloak on :8080, Gateway on :3000), for both the customer and
# admin seed users from keycloak/realm-export.json.
#
# AUTH-01 (self-registration) is a browser form flow in Keycloak, not a JSON
# API, so it isn't scripted here — verify manually via
# http://localhost:8080/realms/internstore/account or the frontend's login
# page with "Register" enabled.
#
# Requires: curl, jq. Run after `docker compose up -d`.
set -euo pipefail

KC_URL="http://localhost:8081"
GATEWAY_URL="http://localhost:3000"
REALM="internstore"
CLIENT_ID="internstore-web"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

get_admin_token() {
  curl -sf -X POST "$KC_URL/realms/master/protocol/openid-connect/token" \
    -d "client_id=admin-cli" -d "username=admin" -d "password=admin" \
    -d "grant_type=password" | jq -r .access_token
}

login() {
  local email="$1" password="$2"
  curl -sf -X POST "$KC_URL/realms/$REALM/protocol/openid-connect/token" \
    -d "client_id=$CLIENT_ID" -d "grant_type=password" \
    -d "username=$email" -d "password=$password"
}

for user in "customer@example.com:Customer123:customer" "admin@example.com:Admin123456:admin"; do
  IFS=':' read -r EMAIL PASSWORD EXPECTED_ROLE <<< "$user"
  echo "--- Testing $EMAIL (expected role: $EXPECTED_ROLE) ---"

  # AUTH-02: login
  TOKENS=$(login "$EMAIL" "$PASSWORD") || fail "$EMAIL login"
  ACCESS_TOKEN=$(echo "$TOKENS" | jq -r .access_token)
  REFRESH_TOKEN=$(echo "$TOKENS" | jq -r .refresh_token)
  [ "$ACCESS_TOKEN" != "null" ] || fail "$EMAIL did not receive access_token"
  ROLE_IN_TOKEN=$(echo "$ACCESS_TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | jq -r '.realm_access.roles[]' | grep -E '^(customer|admin)$' || true)
  [ "$ROLE_IN_TOKEN" = "$EXPECTED_ROLE" ] || fail "$EMAIL token role mismatch (got '$ROLE_IN_TOKEN')"
  pass "$EMAIL login (AUTH-02)"

  # AUTH-03: gateway validates external token via JWKS and mints internal token
  ME=$(curl -sf "$GATEWAY_URL/me" -H "Authorization: Bearer $ACCESS_TOKEN") || fail "$EMAIL gateway /me"
  GW_ROLE=$(echo "$ME" | jq -r .role)
  INTERNAL_TOKEN=$(echo "$ME" | jq -r .internalToken)
  [ "$GW_ROLE" = "$EXPECTED_ROLE" ] || fail "$EMAIL gateway role mismatch"
  [ "$INTERNAL_TOKEN" != "null" ] || fail "$EMAIL did not receive internal token"
  pass "$EMAIL gateway JWKS validation + internal token mint (AUTH-03)"

  # AUTH-04: change password via Admin API (self-service is the Account
  # Console UI; this simulates the outcome for automated testing)
  ADMIN_TOKEN=$(get_admin_token)
  USER_ID=$(curl -sf "$KC_URL/admin/realms/$REALM/users?email=$EMAIL" \
    -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.[0].id')
  NEW_PASSWORD="${PASSWORD}New1"
  curl -sf -X PUT "$KC_URL/admin/realms/$REALM/users/$USER_ID/reset-password" \
    -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
    -d "{\"type\":\"password\",\"value\":\"$NEW_PASSWORD\",\"temporary\":false}" \
    || fail "$EMAIL password reset"

  login "$EMAIL" "$NEW_PASSWORD" >/dev/null || fail "$EMAIL login with new password"
  pass "$EMAIL new password works (AUTH-04)"
  if login "$EMAIL" "$PASSWORD" >/dev/null 2>&1; then
    fail "$EMAIL old password still works after change"
  fi
  pass "$EMAIL old password rejected (AUTH-04)"

  # AUTH-05: logout revokes the refresh token
  curl -sf -X POST "$KC_URL/realms/$REALM/protocol/openid-connect/logout" \
    -d "client_id=$CLIENT_ID" -d "refresh_token=$REFRESH_TOKEN" \
    || fail "$EMAIL logout"
  REFRESH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "$KC_URL/realms/$REALM/protocol/openid-connect/token" \
    -d "client_id=$CLIENT_ID" -d "grant_type=refresh_token" -d "refresh_token=$REFRESH_TOKEN")
  [ "$REFRESH_RESPONSE" = "400" ] || fail "$EMAIL refresh token still usable after logout (got $REFRESH_RESPONSE)"
  pass "$EMAIL refresh token revoked on logout (AUTH-05)"

  # Restore original password so the script is re-runnable
  curl -sf -X PUT "$KC_URL/admin/realms/$REALM/users/$USER_ID/reset-password" \
    -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
    -d "{\"type\":\"password\",\"value\":\"$PASSWORD\",\"temporary\":false}" \
    || fail "$EMAIL password restore"
done

echo "All AUTH-02..05 checks passed."
