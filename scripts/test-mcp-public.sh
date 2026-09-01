#!/usr/bin/env bash
# Phase 3: live check of the public MCP door (nginx /api/mcp).
#
# An external MCP client (here: the `mcp` SDK's own ClientSession) connects
# to https://localhost:8443/api/mcp with a Firebase ID token as the Bearer.
# nginx exchanges it for an internal token and adds X-MCP-Public; the
# gateway serves the customer tool tier and nothing else — an admin's own
# token gets the SAME customer tier through this door (ops/telemetry/
# security tools are mesh-only).
#
# Requires: curl, jq, docker compose up (nginx, mcp-gateway, auth-backend,
# firebase-emulator, orders/catalog/inventory + ai-db, and real ADC for the
# gateway's embedding call in search_products). Reuses services/mcp-gateway's
# uv venv for the `mcp` client library.
set -euo pipefail

EMULATOR="http://localhost:9099"
GATEWAY="https://localhost:8443/api/mcp"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_ROOT/services/mcp-gateway/.venv/bin/python"

fail() { echo "FAIL: $1" >&2; exit 1; }

login() {
  curl -sf -X POST "$EMULATOR/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$1\",\"password\":\"$2\",\"returnSecureToken\":true}" | jq -r .idToken
}

check_door() {
  local label="$1" token="$2"
  echo "--- $label ---"
  MCP_URL="$GATEWAY" MCP_TOKEN="$token" "$PY" - <<'PY'
import asyncio, os, ssl
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import httpx

async def main():
    def factory(*, headers=None, timeout=None, auth=None):
        return httpx.AsyncClient(headers=headers, timeout=timeout, verify=False)  # self-signed dev cert
    url, tok = os.environ["MCP_URL"], os.environ["MCP_TOKEN"]
    async with streamablehttp_client(url, headers={"Authorization": f"Bearer {tok}"}, httpx_client_factory=factory) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = {t.name for t in (await s.list_tools()).tools}
    shopping = {"get_cart", "add_to_cart", "search_products", "search_help"}
    ops = {"get_visit_log", "get_pending_orders", "get_active_incidents", "get_active_users"}
    assert shopping <= names, f"missing shopping tools: {shopping - names}"
    assert not (names & ops), f"ops tools leaked through the public door: {names & ops}"
    print(f"  ok — {len(names)} tools, customer tier only")

asyncio.run(main())
PY
}

CUST_TOKEN=$(login "customer@example.com" "Customer123")
[ "$CUST_TOKEN" != "null" ] || fail "customer login"
check_door "customer via public door" "$CUST_TOKEN"

ADMIN_TOKEN=$(login "admin@example.com" "Admin123456")
[ "$ADMIN_TOKEN" != "null" ] || fail "admin login"
check_door "admin via public door (must still be customer tier)" "$ADMIN_TOKEN"

echo
echo "--- discovery metadata (unauthenticated) ---"
curl -sk "$GATEWAY/.well-known/oauth-protected-resource" | jq -e '.authorization_servers[0] | startswith("https://securetoken.google.com/")' >/dev/null \
  || fail "protected-resource metadata missing/wrong"
echo "  ok"

echo
echo "PASS"
