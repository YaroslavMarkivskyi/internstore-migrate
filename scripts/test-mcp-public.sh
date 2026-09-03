#!/usr/bin/env bash
# Phase 3: live check of the public MCP door — the full OAuth 2.1 dance
# (dynamic client registration -> /authorize -> Firebase login -> code ->
# /token) against the running stack, then an MCP tool call with the Bearer.
#
# The Gateway runs its own small OAuth 2.1 Authorization Server (issuer =
# https://localhost:8443); identity at /authorize is federated to the
# Firebase emulator. A public caller always gets the customer tool tier —
# even an admin login here yields no ops/telemetry/security tools.
#
# Requires: curl, jq, docker compose up (nginx, mcp-gateway, auth-backend,
# firebase-emulator, orders/catalog/inventory + ai-db, real ADC for the
# gateway). Reuses services/mcp-gateway's uv venv for the `mcp` client lib.
set -euo pipefail

BASE="https://localhost:8443"
REDIRECT="http://localhost:9876/cb"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_ROOT/services/mcp-gateway/.venv/bin/python"
C=(curl -sk)

fail() { echo "FAIL: $1" >&2; exit 1; }
qs() { sed -n "s/.*[?&]$2=\([^&\"]*\).*/\1/p" <<<"$1"; }

pkce() {
  VERIFIER=$(head -c 48 /dev/urandom | base64 | tr '+/' '-_' | tr -d '=\n')
  CHALLENGE=$(printf '%s' "$VERIFIER" | openssl dgst -binary -sha256 | base64 | tr '+/' '-_' | tr -d '=\n')
}

get_token() { # $1 = email  $2 = password
  local client_id code_loc code
  client_id=$("${C[@]}" -X POST "$BASE/register" -H 'content-type: application/json' \
    -d "{\"redirect_uris\":[\"$REDIRECT\"],\"token_endpoint_auth_method\":\"none\",\"grant_types\":[\"authorization_code\",\"refresh_token\"],\"response_types\":[\"code\"]}" \
    | jq -r .client_id)
  [ -n "$client_id" ] && [ "$client_id" != null ] || fail "DCR failed"

  pkce
  local login_loc rid
  login_loc=$("${C[@]}" -o /dev/null -D - "$BASE/authorize?response_type=code&client_id=$client_id&redirect_uri=$REDIRECT&code_challenge=$CHALLENGE&code_challenge_method=S256&scope=mcp:shopping&state=xyz" \
    | tr -d '\r' | sed -n 's/^location: //Ip')
  rid=$(qs "$login_loc" rid)
  [ -n "$rid" ] || fail "/authorize did not redirect to login"

  code_loc=$("${C[@]}" -o /dev/null -D - -X POST "$BASE/oauth/login" \
    --data-urlencode "rid=$rid" --data-urlencode "email=$1" --data-urlencode "password=$2" \
    | tr -d '\r' | sed -n 's/^location: //Ip')
  code=$(qs "$code_loc" code)
  [ -n "$code" ] || fail "login did not yield an auth code (check credentials)"

  "${C[@]}" -X POST "$BASE/token" \
    --data-urlencode "grant_type=authorization_code" --data-urlencode "code=$code" \
    --data-urlencode "redirect_uri=$REDIRECT" --data-urlencode "client_id=$client_id" \
    --data-urlencode "code_verifier=$VERIFIER" | jq -r .access_token
}

check_tier() { # $1 = label  $2 = access token
  echo "--- $1 ---"
  MCP_TOKEN="$2" "$PY" - <<'PY'
import asyncio, os, httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    def factory(*, headers=None, timeout=None, auth=None):
        return httpx.AsyncClient(headers=headers, timeout=timeout, verify=False)
    async with streamablehttp_client(
        "https://localhost:8443/mcp",
        headers={"Authorization": f"Bearer {os.environ['MCP_TOKEN']}"},
        httpx_client_factory=factory,
    ) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = {t.name for t in (await s.list_tools()).tools}
    shopping = {"get_cart", "add_to_cart", "search_products", "search_help"}
    ops = {"get_visit_log", "get_pending_orders", "get_active_incidents", "get_active_users"}
    assert shopping <= names, f"missing shopping tools: {shopping - names}"
    assert not (names & ops), f"ops tools leaked: {names & ops}"
    print(f"  ok — {len(names)} tools, customer tier only")

asyncio.run(main())
PY
}

echo "--- discovery (unauthenticated) ---"
"${C[@]}" "$BASE/.well-known/oauth-authorization-server" | jq -e '.token_endpoint and .registration_endpoint' >/dev/null || fail "AS metadata"
"${C[@]}" "$BASE/.well-known/oauth-protected-resource/mcp" | jq -e '.authorization_servers[0]' >/dev/null || fail "PRM"
"${C[@]}" "$BASE/.well-known/jwks.json" | jq -e '.keys[0].kty == "RSA"' >/dev/null || fail "JWKS"
echo "  ok"

check_tier "customer via public OAuth" "$(get_token customer@example.com Customer123)"
check_tier "admin via public OAuth (still customer tier)" "$(get_token admin@example.com Admin123456)"

echo
echo "PASS"
