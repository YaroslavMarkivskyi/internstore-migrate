# MCP Gateway

Exposes InternStore's domain data (Orders, Inventory, Catalog, Telemetry,
Security, Chat) as [MCP](https://modelcontextprotocol.io) tools over HTTP,
so any MCP-compatible AI agent — starting with the AI Assistant — calls one
consistent tool registry instead of a hand-rolled HTTP client per domain
service.

One `/mcp` route, two doors, one tool-execution core (`src/mcp_gateway/mcp_server.py`'s `_identify`):

- **in-mesh** — an `X-Internal-Token` (the AI Assistant's ADK agents, or any
  in-mesh client). Verified per request, forwarded downstream unchanged so
  `add_to_cart`/`get_cart` ownership resolves against the real customer, not
  the Gateway (STR-146). No nginx route.
- **public** — an OAuth 2.1 access token this service issues itself (see
  below). Fronted by the external nginx Gateway. Always the **customer** tool
  tier — ops/telemetry/security tools are mesh-only.

## Protocol endpoint

A real [MCP](https://modelcontextprotocol.io) server (`mcp` 1.x,
`mcp.server.lowlevel.Server`) over the **Streamable HTTP** transport at
`POST /mcp` (JSON-RPC: `initialize`, `tools/list`, `tools/call`). `mcp` is
pinned to 1.x because the AI Assistant consumes this through Google ADK's
`McpToolset`, which needs the 1.x client.

In-mesh, with an internal token:

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(
    "http://mcp-gateway:8000/mcp", headers={"X-Internal-Token": TOKEN}
) as (r, w, _):
    async with ClientSession(r, w) as s:
        await s.initialize()
        print(await s.list_tools())
```

### Public door — OAuth 2.1

The Gateway runs a small **OAuth 2.1 Authorization Server** co-located with
the resource server (`src/mcp_gateway/oauth/`). Issuer = the external nginx
Gateway (`PUBLIC_BASE_URL`). It implements what a spec-compliant MCP client
(Claude Desktop, MCP Inspector) needs to connect on its own:

| Endpoint | Purpose |
|---|---|
| `/.well-known/oauth-protected-resource/mcp` | RFC 9728 — resource → authorization server |
| `/.well-known/oauth-authorization-server` | RFC 8414 — AS metadata |
| `/register` | RFC 7591 — dynamic client registration |
| `/authorize` → `/oauth/login` → redirect | RFC 6749 §4.1 + PKCE; identity **federated to Firebase** (Identity Toolkit REST / the emulator) |
| `/token` | authorization-code + refresh; RS256 JWT, `aud` = the MCP resource, scope `mcp:shopping` |
| `/.well-known/jwks.json` | RFC 7517 — verification key |

`RequireAuthMiddleware` guards `/mcp` for non-internal callers and answers
`401` + `WWW-Authenticate: Bearer resource_metadata="…"`. A validated token's
`sub` → a freshly minted internal token for the downstream fan-out; the
scope pins the tier to `customer` whatever the user's Firebase role.

nginx rate-limits `/mcp` (`limit_req_zone mcp_public`, 60 r/min per IP).
See [scripts/test-mcp-public.sh](../../scripts/test-mcp-public.sh) for the
full flow driven with `curl`.

**Demo-scale shortcuts:** clients/codes/refresh tokens are in-memory (a
restart = re-register + re-auth); the RS256 key is ephemeral unless
`OAUTH_SIGNING_KEY_PEM` is set; the Firebase ID token from the login step is
decoded, not cryptographically verified (the password exchange is the auth,
and the emulator signs with `alg: none`) — production would verify via the
Firebase Admin SDK / Google JWKS.

## Tool catalog

Each tool is a thin wrapper around an `httpx` call to the owning domain
service (`src/mcp_gateway/tools/<domain>.py`), authenticated the same way
every other inter-service call in this repo is.

### Orders

| Tool | Arguments | Returns |
|---|---|---|
| `get_order_status` | `order_id: str` | Order status, items, timestamps, contact info |
| `list_customer_orders` | `customer_id: str`, `limit: int = 5` | Recent orders with status |
| `get_pending_orders` | `older_than_minutes: int = 60` | Orders stuck in `pending`, admin use |
| `get_cart` | — | Caller's own cart contents. Scoped entirely by the forwarded token's `sub` — no `customer_id` argument exists to hallucinate |
| `add_to_cart` | `product_id: str`, `quantity: int` | Adds to the caller's own cart (accumulates existing quantity) |
| `remove_from_cart` | `product_id: str` | Removes a product from the caller's own cart |

### Inventory

| Tool | Arguments | Returns |
|---|---|---|
| `check_availability` | `product_id: str`, `quantity: int` | Available stock across warehouses |
| `get_stock_levels` | `warehouse_id: str` | All products and quantities in a warehouse |
| `get_unavailable_items` | — | Items flagged `is_unavailable` (temperature violations) |

### Catalog

| Tool | Arguments | Returns |
|---|---|---|
| `search_products` | `query: str`, `limit: int = 5`, `filters: {price_min, price_max, category}? = None` | Semantic search via pgvector — queries AI Assistant's own `product_embeddings` table directly (see `AI_DB_URL`), not a Catalog HTTP call. Filters are plain SQL predicates applied after the vector ordering |
| `get_product` | `product_id: str` | Full product details including temperature range |
| `list_categories` | — | All categories |

### Telemetry

| Tool | Arguments | Returns |
|---|---|---|
| `get_store_temperature` | `store_id: str` | Current temperature + violation status |
| `get_temperature_readings` | `store_id: str`, `period: "week"\|"month"\|"3months"\|"all" = "week"` | Historical timeseries |
| `get_active_incidents` | — | Open temperature incidents across every store |

### Security (admin use)

| Tool | Arguments | Returns |
|---|---|---|
| `get_visit_log` | `warehouse_id: str`, `date_from: str`, `date_to: str` | Access log with video URLs |
| `get_active_users` | — | Registered employees/suppliers with access rules |

### Chat (admin use)

| Tool | Arguments | Returns |
|---|---|---|
| `get_room_summary` | `room_id: str`, `limit: int = 20` | Last N messages from a chat room |
| `list_active_rooms` | — | Rooms with unread messages |

## Usage from AI Assistant

AI Assistant's shopping + ops agents (Google ADK `LlmAgent`) are this
service's consumers, each via an ADK `McpToolset` pointed at `/mcp` with a
`tool_filter` — the shopping agent sees only the cart-scoped and
customer-safe reads, the ops agent only the read-only admin tools. The
customer's own internal-token is forwarded on every call (the toolset's
`header_provider` refreshes it against auth-backend when it's near its 60s
TTL). No checkout/payment tool exists in the registry at all — see
`src/mcp_gateway/router.py`'s `build_tool_registry` for the enforced
boundary. This boundary is structural (no registry entry to route to), not a
prompt instruction, so it holds regardless of which model calls it —
verified in `tests/test_checkout_tool_absent.py` and
`services/ai-assistant/evals/adk/test_adk_evals.py`. Any MCP-compatible
client can otherwise call this service directly over the `/mcp` endpoint per
invocation.

## Gemini migration (STR-161b)

`search_products` (`tools/catalog.py`) embeds the query via Gemini's
`gemini-embedding-001` through the Gemini Enterprise Agent Platform (Vertex
AI's Cloud Next 2026 rebrand), not OpenAI's `text-embedding-3-small`
anymore. See `services/ai-assistant/README.md`'s "Gemini migration" section
for the full rationale (dimensionality choice, auth, re-embedding) — this
service's `EMBEDDING_DIMENSIONS`/`embedding_dimensions` must stay in sync
with ai-assistant's, since both read/write the same `product_embeddings`
table.

## Demo query

"Find all warehouses with temperature violations and check if affected
products have pending orders" — a multi-tool chain: `get_active_incidents`
→ `get_unavailable_items` → `get_pending_orders`.

## Verification

```bash
cd services/mcp-gateway && uv run pytest

docker compose up -d --build mcp-gateway
```

## Known, accepted gaps

- **`get_unavailable_items` and `get_pending_orders` filter client-side.**
  Inventory has no cross-stock query for `is_unavailable`, and Orders has no
  status/age filter on `GET /orders/admin` — both tools pull the admin list
  and filter in this service instead. Fine for a low-frequency, admin-facing
  tool; would need a real query param upstream if this became a hot path.
- **No JSON Schema argument validation before dispatch.** The `tools/call`
  handler runs with `validate_input=False` and relies on the target
  function's own required-keyword arguments (bad shape → an `isError` tool
  result) rather than validating `arguments` against each tool's declared
  `inputSchema` up front — deliberately, so `tools/orders.py`'s `_require_uuid`
  / `_require_sane_quantity` can return a message the model can actually act
  on instead of a raw jsonschema error.
- **`schema.py` `TOOL_SPECS` is still hand-maintained** rather than generated
  from the tool-client method signatures — a known "generate it" follow-up.
- **The public OAuth AS is demo-scale** — in-memory client/code/token
  stores, an ephemeral signing key, and the federated Firebase ID token is
  decoded rather than verified. See the "Public door — OAuth 2.1" section
  above for the full list. The *protocol* is complete (DCR, auth-code+PKCE,
  refresh, metadata, JWKS); a production deployment would swap the storage +
  key + Firebase verification, or front it with a real AS (Hydra / Auth0).
