#!/usr/bin/env bash
# End-to-end verification of the Security service (STR-127) through the
# real gateway and real Keycloak-issued tokens — not the in-process JWTs
# the pytest suite mints. Security has no Kafka dependency (access control
# is synchronous by nature), so this script only needs the gateway, auth
# stack, and security/security-db/mock-camera up.
#
# Covers:
#   1. Register an employee (POST /users, fingerprint).
#   2. Correct credential -> allowed: true, visit_log row created,
#      video_url set.
#   3. Wrong credential -> allowed: false, denial_reason set.
#   4. Revoke the user (PATCH /users/{id} is_active=false) -> subsequent
#      attempt with the correct credential is denied.
#
# Requires: curl, jq, docker compose. Run after
# `docker compose up -d --build` (needs security-db, security, mock-camera,
# nginx, keycloak, auth-backend all healthy).
set -euo pipefail

KC_URL="http://localhost:8081"
SECURITY_URL="https://localhost:8443/api/security"
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

ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$ADMIN_TOKEN" != "null" ] || fail "admin login did not return an access token"

WAREHOUSE_ID="11111111-1111-1111-1111-$(printf '%012d' "$RANDOM")"
CREDENTIAL="fp-template-saga-$$-$RANDOM"

echo "=== 1. Register an employee (fingerprint) ==="
USER_ID=$($CURL -X POST "$SECURITY_URL/users" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"Saga Employee\", \"auth_type\": \"fingerprint\", \"credential\": \"$CREDENTIAL\", \"warehouse_ids\": [\"$WAREHOUSE_ID\"]}" \
  | jq -r .id)
[ -n "$USER_ID" ] && [ "$USER_ID" != "null" ] || fail "could not register employee"
pass "employee $USER_ID registered with access to warehouse $WAREHOUSE_ID"

echo "=== 2. Correct credential -> allowed ==="
RESULT=$($CURL -X POST "$SECURITY_URL/auth/fingerprint" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"warehouse_id\": \"$WAREHOUSE_ID\", \"fingerprint_template\": \"$CREDENTIAL\"}")
[ "$(echo "$RESULT" | jq -r .allowed)" = "true" ] || fail "expected allowed:true, got $RESULT"
[ "$(echo "$RESULT" | jq -r .user_id)" = "$USER_ID" ] || fail "expected user_id $USER_ID, got $RESULT"
pass "correct fingerprint -> allowed: true"

VISIT_LOG=$($CURL "$SECURITY_URL/visit-log?warehouse_id=$WAREHOUSE_ID&success=true" -H "Authorization: Bearer $ADMIN_TOKEN")
[ "$(echo "$VISIT_LOG" | jq 'length')" -ge 1 ] || fail "no successful visit_log row found"
VIDEO_URL=$(echo "$VISIT_LOG" | jq -r '.[0].video_url')
[ -n "$VIDEO_URL" ] && [ "$VIDEO_URL" != "null" ] || fail "video_url was not set on the visit_log row"
pass "visit_log row created with video_url=$VIDEO_URL"

echo "=== 3. Wrong credential -> denied ==="
RESULT=$($CURL -X POST "$SECURITY_URL/auth/fingerprint" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"warehouse_id\": \"$WAREHOUSE_ID\", \"fingerprint_template\": \"not-$CREDENTIAL\"}")
[ "$(echo "$RESULT" | jq -r .allowed)" = "false" ] || fail "expected allowed:false, got $RESULT"
DENIAL_REASON=$(echo "$RESULT" | jq -r .denial_reason)
[ -n "$DENIAL_REASON" ] && [ "$DENIAL_REASON" != "null" ] || fail "expected a denial_reason, got $RESULT"
pass "wrong fingerprint -> allowed: false, denial_reason: $DENIAL_REASON"

echo "=== 4. Revoke the user -> subsequent attempt denied ==="
$CURL -X PATCH "$SECURITY_URL/users/$USER_ID" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d '{"is_active": false}' >/dev/null
pass "user $USER_ID revoked (is_active=false)"

RESULT=$($CURL -X POST "$SECURITY_URL/auth/fingerprint" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"warehouse_id\": \"$WAREHOUSE_ID\", \"fingerprint_template\": \"$CREDENTIAL\"}")
[ "$(echo "$RESULT" | jq -r .allowed)" = "false" ] || fail "expected allowed:false after revoke, got $RESULT"
[ "$(echo "$RESULT" | jq -r .denial_reason)" = "inactive user" ] || fail "expected denial_reason 'inactive user', got $RESULT"
pass "revoked user's correct fingerprint -> allowed: false, denial_reason: inactive user"

echo
echo "All security-saga verification checks passed against the real gateway."
