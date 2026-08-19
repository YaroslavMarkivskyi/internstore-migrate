# MCP Gateway

Exposes InternStore's domain data (Orders, Inventory, Catalog, Telemetry,
Security, Chat) as [MCP](https://modelcontextprotocol.io) tools over HTTP,
so any MCP-compatible AI agent — starting with the AI Assistant — calls one
consistent tool registry instead of a hand-rolled HTTP client per domain
service.

Internal-only: no nginx route, never reachable from the browser. Every
request (from AI Assistant, or any future client) must carry the same
`X-Internal-Token` every other domain service requires. **STR-146:** the
Gateway no longer mints its own token for outbound calls — it forwards the
caller's own already-verified token unchanged to whichever domain service a
tool call fans out to (see `src/mcp_gateway/auth.py`'s
`get_raw_internal_token`). This is what makes `add_to_cart`/`get_cart`'s
ownership check mean anything: a tool call runs as whoever actually called
`/mcp/tools/call` (a customer, a guest, an admin, or AI Assistant's own
`assistant`-role token), never as a fixed Gateway identity.

## Protocol endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/mcp` | Server info: name, version, capabilities |
| GET | `/mcp/tools` | Full tool catalog with JSON Schema input for each tool |
| POST | `/mcp/tools/call` | Execute a tool: `{"name": "...", "arguments": {...}}` |
| GET | `/mcp/sse` | SSE handshake — emits an `endpoint` event pointing back at `/mcp/tools/call` |

```bash
curl -s http://mcp-gateway:8000/mcp/tools -H "X-Internal-Token: $TOKEN" | jq

curl -s http://mcp-gateway:8000/mcp/tools/call \
  -H "X-Internal-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "get_order_status", "arguments": {"order_id": "<uuid>"}}'
```

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

**STR-146:** AI Assistant's shopping ReAct loop (`react_loop.py`) is this
service's first real consumer — it fetches `GET /mcp/tools`, filters to
exactly `search_products`/`get_cart`/`add_to_cart`/`remove_from_cart`, builds
Gemini's `FunctionDeclaration`/`Tool` request shape from those specs
(**STR-161b:** was OpenAI's function-calling `tools` parameter before the
Gemini migration — `TOOL_SPECS`' plain JSON Schema in `schema.py` is
unchanged either way, only the caller-side translation differs), and forwards
the customer's own internal-token (refreshed via auth-backend if the loop
outlives its 60s TTL) on every `POST /mcp/tools/call`. The Gateway's full
16-tool catalog still exists for other admin-facing use, but nothing outside
that 4-tool subset is ever offered to the shopping agent's model, and no
checkout/payment tool exists in the registry at all — see
`src/mcp_gateway/router.py`'s `build_tool_registry` for the enforced
boundary. This boundary is structural (no registry entry to route to), not a
prompt instruction or a model-specific behavior, so it holds the same way
regardless of which model calls it — re-verified specifically against Gemini
in `tests/test_checkout_tool_absent.py` and
`services/ai-assistant/tests/test_react_loop.py`'s
`test_a_hallucinated_checkout_tool_call_is_surfaced_as_an_error_not_executed_as_success`,
plus the live adversarial-prompt check in
`scripts/test-shopping-agent-gemini-checkout.sh`. Any MCP-compatible client
(Claude Desktop, a custom agent) can otherwise call this service directly:
fetch `GET /mcp/tools` for the schema, then `POST /mcp/tools/call` per
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
- **No JSON Schema argument validation before dispatch.** `POST
  /mcp/tools/call` relies on the target function's own required-keyword
  arguments (`TypeError` → `422`) rather than validating `arguments` against
  each tool's declared `input_schema` up front — the schema in `GET
  /mcp/tools` is documentation-quality, not a validation gate yet.
- **`/mcp/sse` is a one-shot handshake, not a live push channel.** It emits
  a single `endpoint` event and lets the client know where to `POST` tool
  calls; results still return over that POST's own response body, not
  streamed back down the SSE connection.
