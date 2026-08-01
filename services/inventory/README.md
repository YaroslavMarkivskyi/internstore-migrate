# inventory

Stocks and stock items for InternStore. Second domain service split out of
the monolith — chosen because it's the producer of `StockReserved` /
`StockReservationFailed` events Orders will consume in the checkout saga, and
the owner of the one synchronous endpoint in the system
(`POST /stocks/check-availability`, called by Orders at checkout). Getting
Inventory's read/write surface in place now means Orders can build against it
once it exists.

Same stack as [services/catalog](../catalog): Python/FastAPI/SQLAlchemy
(async)/Alembic, its own Postgres database with zero shared tables, and the
same internal-token verification pattern (see [src/inventory/auth.py](src/inventory/auth.py),
which mirrors `services/catalog/src/catalog/auth.py`).

## Data model

- `Stock` — a warehouse/store. `temperature` is nullable/pending until a
  future Telemetry subscription populates it — not implemented here.
- `StockItem` — quantity of a product at a given stock. `product_id` is a
  bare UUID referencing Catalog's `Product.id`; there is no foreign key to
  Catalog's database, and this service never validates the product exists.

## Endpoints

- `GET /health` — liveness check.
- `POST /stocks` — admin-only. Body: `{"name": "..."}` (2-100 chars,
  unique), `temperature` optional. 409 on duplicate name.
- `GET /stocks` — public, list stocks with `temperature` (`null` until
  Telemetry integration lands).
- `GET /stocks/{id}/items` — public, list stock items for one stock. 404 if
  the stock doesn't exist. (STO-02)
- `GET /items` — public, consolidated quantity per product across all
  stocks. Optional filters: `stock_id`, `min_quantity`, `max_quantity`.
  Filtering by Catalog attributes like category/price is explicitly out of
  scope here — Inventory doesn't own that data; composing it belongs to a
  future Gateway/BFF ticket. (STO-02)
- `POST /stocks/{id}/items` — admin-only. Body: `{"product_id", "quantity"}`
  (`quantity` > 0). Increments existing quantity for that product at that
  stock, or creates a new row. 404 on unknown stock. (STO-01)
- `POST /stocks/{id}/items/{itemId}/move` — admin-only. Body:
  `{"to_stock_id", "quantity"}`. Moves quantity from `itemId` (must belong to
  `{id}`) to the destination stock, upserting there. 404 if the stock or item
  doesn't exist, 422 on insufficient quantity or same-stock move. (STO-03)
- `POST /stocks/check-availability` — the sync contract Orders calls at
  checkout. Requires a valid `X-Internal-Token` (any role — customer, admin,
  or guest — since any of them can check out; see
  [services/orders](../orders)), forwarded by Orders from the caller's own
  token rather than a synthetic Orders-service identity. Body:
  `{"items": [{"product_id", "quantity"}, ...]}`. Returns per-product
  `available` (summed across all stocks) and `sufficient`, plus a top-level
  `sufficient` that's true only if every line item is. Documented in
  [libs/contracts/inventory/check-availability.md](../../libs/contracts/inventory/check-availability.md).

Not in scope for this ticket (see the task write-up): reservation
(ORDC-04) and its Kafka consumer/producer wiring with Orders, subscribing to
`TemperatureThresholdViolated` from Telemetry, and the STO-01 fingerprint/NFC
part of EP-08/09.

## Auth

Every write endpoint validates the `X-Internal-Token` header locally — HMAC
(HS256) signature, `iss`, `exp` — against the same shared secret
`auth-backend` mints with (`INTERNAL_TOKEN_SECRET`). This service never
trusts `X-User-Id`/`X-User-Role` headers directly and never calls back to
Keycloak or auth-backend.

## Local dev without Docker

```bash
cd services/inventory
cp .env.example .env   # point DATABASE_URL at a local Postgres
uv sync
uv run alembic upgrade head
uv run uvicorn inventory.main:create_app --factory --reload
```

Run tests (self-contained, in-memory SQLite, no DB needed):

```bash
uv run pytest
```

## Via docker compose

```bash
docker compose up -d inventory-db inventory
```

Reachable through nginx at `/api/inventory/*` (see
[nginx/nginx.conf](../../nginx/nginx.conf)), not exposed on the host
directly — same pattern as catalog.

End-to-end smoke test against the real gateway with real Keycloak-issued
tokens (401/403/201/200 through nginx, quantity accumulation, move, and all
three check-availability outcomes):

```bash
docker compose up -d --build inventory-db inventory nginx
./scripts/verify-inventory-gateway.sh
```

## Migrations

New migration after changing `src/inventory/models.py`:

```bash
DATABASE_URL=postgresql+asyncpg://inventory:inventory@localhost:5434/inventory \
  uv run alembic revision --autogenerate -m "describe the change"
```
