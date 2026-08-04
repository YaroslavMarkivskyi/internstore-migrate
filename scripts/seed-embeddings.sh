#!/usr/bin/env bash
# Triggers an initial embedding build for every existing product.
#
# AI Assistant's product_embeddings table is populated lazily — only by
# Catalog's ProductUpdated event, fired from PATCH /products/{id} (see
# services/catalog/src/catalog/routers/products.py). A fresh stack has no
# products embedded yet, so this re-sends each product's own current name
# unchanged, just to trigger that event — see docs/EVENT_BROKER.md's
# AI Assistant dev-gaps note.
#
# Requires: curl, jq, docker compose. Run after `docker compose up -d`
# with at least one product already created (e.g. via the frontend/admin
# UI or scripts/verify-gateway.sh).
set -euo pipefail

KC_URL="http://localhost:8081"
GATEWAY_URL="https://localhost:8443/api/catalog"
REALM="internstore"
CLIENT_ID="internstore-web"
CURL="curl -sk"

login() {
  curl -sfk -X POST "$KC_URL/realms/$REALM/protocol/openid-connect/token" \
    -d "client_id=$CLIENT_ID" -d "grant_type=password" \
    -d "username=$1" -d "password=$2" | jq -r .access_token
}

ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$ADMIN_TOKEN" != "null" ] && [ -n "$ADMIN_TOKEN" ] || {
  echo "FAIL: admin login did not return an access token" >&2
  exit 1
}

PRODUCT_IDS=$($CURL "$GATEWAY_URL/products" | jq -r '.[].id')
if [ -z "$PRODUCT_IDS" ]; then
  echo "No products found — nothing to seed."
  exit 0
fi

COUNT=0
while IFS= read -r PRODUCT_ID; do
  NAME=$($CURL "$GATEWAY_URL/products/$PRODUCT_ID" | jq -r .name)
  $CURL -X PATCH "$GATEWAY_URL/products/$PRODUCT_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
    -d "$(jq -n --arg name "$NAME" '{name: $name}')" >/dev/null
  COUNT=$((COUNT + 1))
done <<< "$PRODUCT_IDS"

echo "Triggered ProductUpdated for $COUNT product(s) — AI Assistant will re-embed them shortly."
