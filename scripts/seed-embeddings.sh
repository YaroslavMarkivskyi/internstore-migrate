#!/usr/bin/env bash
# Triggers an initial embedding build for every existing product.
#
# AI Assistant's product_embeddings table is populated from Catalog's
# ProductUpdated event, now fired on both POST /products (creation) and
# PATCH /products/{id} (see services/catalog/src/catalog/routers/products.py).
# So this script is only needed for products that were created *before*
# that POST-side event existed: it re-sends each product's own current
# name unchanged via PATCH, just to trigger a re-embed — see
# docs/EVENT_BROKER.md's AI Assistant dev-gaps note.
#
# Requires: curl, jq, docker compose. Run after `docker compose up -d`
# with at least one such legacy product present (e.g. from an older
# scripts/verify-gateway.sh run).
set -euo pipefail

FIREBASE_AUTH_EMULATOR_URL="http://localhost:9099"
GATEWAY_URL="https://localhost:8443/api/catalog"
FIREBASE_PROJECT_ID="internstore-dev"
CURL="curl -sk"

login() {
  curl -sf -X POST "$FIREBASE_AUTH_EMULATOR_URL/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$1\",\"password\":\"$2\",\"returnSecureToken\":true}" | jq -r .idToken
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
