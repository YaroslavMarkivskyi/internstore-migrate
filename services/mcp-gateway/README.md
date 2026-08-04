# MCP Gateway

Exposes InternStore's domain data (Orders, Inventory, Catalog, Telemetry,
Security, Chat) as [MCP](https://modelcontextprotocol.io) tools over HTTP,
so any MCP-compatible AI agent — starting with the AI Assistant — calls one
consistent tool registry instead of a hand-rolled HTTP client per domain
service.

Internal-only: no nginx route, never reachable from the browser. Every
request (from AI Assistant, or any future client) must carry the same
`X-Internal-Token` every other domain service requires. This service in
turn mints its own token (`sub: mcp-gateway`, `role: admin`) on every
outbound call to a domain service — a single tool call can fan out to
whichever service holds the data, so it needs the same read access an admin
has everywhere, not a narrower per-domain role. See
`src/mcp_gateway/auth.py`.

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

### Inventory

| Tool | Arguments | Returns |
|---|---|---|
| `check_availability` | `product_id: str`, `quantity: int` | Available stock across warehouses |
| `get_stock_levels` | `warehouse_id: str` | All products and quantities in a warehouse |
| `get_unavailable_items` | — | Items flagged `is_unavailable` (temperature violations) |

### Catalog

| Tool | Arguments | Returns |
|---|---|---|
| `search_products` | `query: str`, `limit: int = 5` | Semantic search via pgvector — queries AI Assistant's own `product_embeddings` table directly (see `AI_DB_URL`), not a Catalog HTTP call |
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

`MCP_GATEWAY_URL` is wired into AI Assistant's compose environment
(`http://mcp-gateway:8000`), not yet consumed by its own code — the actual
swap from AI Assistant's direct `OrdersClient` HTTP call to an MCP tool
call, and the OpenAI function-calling `tools` parameter built from
`GET /mcp/tools`, land in a follow-up ticket. Any MCP-compatible client
(Claude Desktop, a custom agent) can otherwise call this service directly:
fetch `GET /mcp/tools` for the schema, then `POST /mcp/tools/call` per
invocation.

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
