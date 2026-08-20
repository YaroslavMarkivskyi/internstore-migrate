# orders

Cart and checkout for InternStore. Third domain service split out of the
monolith, and the first with a real synchronous inter-service call:
`POST /checkout` calls Inventory's `POST /stocks/check-availability`
directly over the compose network (`http://inventory:8000`, bypassing
nginx — the same address nginx itself proxies to; only host port exposure is
restricted, not container-to-container traffic).

This ticket covers only the skeleton and checkout with a plain availability
check. The reservation saga (Kafka `OrderCreated` → `StockReserved` /
`StockReservationFailed`, `PaymentConfirmed`, `ReservationExpired`) is a
separate, later ticket — no stock is reserved or decremented here, and no
Kafka code exists in this service yet even though the `order-events` /
`inventory-events` topics already exist in `docker-compose.yml`. Admin-side
endpoints (ORDA-*), order cancellation, and a real payment provider
integration are likewise out of scope.

Same stack as [services/catalog](../catalog) and
[services/inventory](../inventory): Python/FastAPI/SQLAlchemy (async)/
Alembic, its own Postgres database with zero shared tables, and the same
internal-token verification pattern (see
[src/orders/auth.py](src/orders/auth.py)).

## Data model

- `Cart` / `CartItem` — one cart per `owner_id` (a Firebase `sub` for
  customer/admin, or a `guest_id` minted by auth-backend's guest-session
  fallback for unauthenticated shoppers — see below). `product_id` is a
  bare UUID referencing Catalog's `Product.id`; no foreign key, same
  convention as `inventory.StockItem.product_id`.
- `Order` / `OrderItem` — created at checkout. `status` is a native Postgres
  enum with a single member, `new`, in this ticket — `pending`/`paid`/
  `done`/`cancelled`/`rejected` are added by the saga ticket as an additive
  migration, not a restructuring.
- No price/currency anywhere: `check-availability` doesn't return price and
  nothing in this ticket calls for a total.

## Endpoints

- `GET /health` — liveness check.
- `GET /cart` — the caller's cart. Returns `{"items": []}` if none exists yet
  (no row is created until the first item is added).
- `POST /cart` — add an item (`{"product_id", "quantity"}`, `quantity` > 0).
  Accumulates quantity if the product is already in the cart, same
  convention as Inventory's `receive_stock_item`.
- `PUT /cart/items/{product_id}` — set an item's quantity (`{"quantity"}`).
  404 if the item isn't in the cart.
- `DELETE /cart/items/{product_id}` — remove an item. 404 if not present.
- `POST /checkout` — body: `{"contact_name", "contact_email",
  "contact_phone"?, "payment_method"}`. Calls Inventory's
  `check-availability` with the cart's contents, forwarding the caller's own
  `X-Internal-Token` (not a synthetic Orders identity — see "Auth" below).
  - Cart empty → `422`.
  - Inventory unreachable (timeout/connection error) or returns `5xx` →
    `503 {"detail": "...", "retry_after_seconds": 5}`.
  - Any item insufficient → `409` with the full per-item breakdown from
    Inventory (`product_id`, `requested`, `available`, `sufficient`); no
    `Order` is created, the cart is left untouched.
  - All sufficient → creates an `Order` (`status: "new"`) + `OrderItem`s from
    the cart, clears the cart, returns `201` with the order.
- `GET /orders` — the caller's own orders, most-recent-first.
- `GET /orders/{id}` — order detail. `404` both when the order doesn't exist
  and when it belongs to someone else — deliberately not `403`, so the
  response doesn't leak whether an order id exists at all.

### `/checkout/v2` — Temporal-orchestrated checkout (STR-139)

Additive, parallel path alongside `POST /checkout` above — the existing
Kafka-choreographed saga (STR-124) is completely untouched; this is purely
to evaluate Temporal as an orchestrator before any cutover decision. See
[services/checkout-workflow](../checkout-workflow) and
[docs/adr/0003-temporal-checkout-orchestration.md](../../docs/adr/0003-temporal-checkout-orchestration.md).

- `POST /checkout/v2` — same body/validation as `POST /checkout`. Computes
  the total charge amount server-side from Catalog's current prices, starts
  `CheckoutWorkflow` via a Temporal client (best-effort — `503` if Temporal
  is unreachable, same reasoning as Inventory/Catalog having no
  `depends_on`), then waits inline up to `checkout_v2_wait_seconds` (default
  10s) for the workflow to finish. Cart is cleared once the workflow has
  been started, regardless of outcome — same timing as `/checkout`.
  - Finishes within the wait window → `201 {"workflow_id", "status":
    "confirmed"|"rejected", "order"}`.
  - Still running past the wait window → `202 {"workflow_id", "status":
    "running"}` — poll `GET /checkout/v2/{workflow_id}` for the final result.
- `GET /checkout/v2/{workflow_id}` — current status/result of a workflow
  started above.
- `POST /internal/checkout-workflow/orders`,
  `PATCH /internal/checkout-workflow/orders/{id}/status` — not part of the
  public checkout contract. Called only by checkout-workflow's Temporal
  activities (admin-role internal token), idempotent by the
  workflow-supplied `order_id` / unconditional status set respectively —
  see `routers/checkout_v2.py`'s docstrings for why redelivery is safe on
  each.

## Auth

Every endpoint validates `X-Internal-Token` locally (HMAC HS256, `iss`,
`exp`) against the shared secret, same as catalog/inventory — see
[src/orders/auth.py](src/orders/auth.py). Unlike catalog/inventory, the
valid roles include `guest`: cart and checkout treat `customer`, `admin`,
and `guest` identically, keyed only by the token's `sub`.

### Guest checkout

There's no admin-only distinction anywhere in this service, but cart/
checkout do need to work for people who haven't logged in. That identity
comes entirely from **auth-backend**, not from anything in this service —
see [services/auth-backend/README.md](../auth-backend/README.md#guest-sessions)
for the full mechanism (Redis-backed `guest_id`, `is_guest_id` cookie,
7-day TTL). From Orders' point of view, a guest request just arrives with a
normal internal token where `role == "guest"`; there is no guest-specific
code path here.

One consequence worth knowing: guest checkout works, but `GET /orders` and
`GET /orders/{id}` do not — those paths aren't in auth-backend's
guest-allowed list, so a guest gets a `401` there and needs to register/log
in to see past orders.

### Internal-token forwarding to Inventory

Inventory's `check-availability` endpoint validates `X-Internal-Token` just
like any other Inventory route (any role — customer/admin/guest — since any
of them can check out). Orders forwards the *caller's own* token on the
outbound call rather than minting a new one, so Inventory sees the actual
checking-out user's identity, not a synthetic Orders-service identity. This
closes a defense-in-depth gap: `check-availability` previously had no auth
check at all.

## Local dev without Docker

```bash
cd services/orders
cp .env.example .env   # point DATABASE_URL at a local Postgres, INVENTORY_BASE_URL at a running Inventory
uv sync
uv run alembic upgrade head
uv run uvicorn orders.main:create_app --factory --reload
```

Run tests (self-contained, in-memory SQLite, no DB or Inventory needed —
the Inventory client is swapped for a fake via FastAPI's
`dependency_overrides`, plus one `respx`-based test that checks the actual
outbound HTTP request shape):

```bash
uv run pytest
```

## Via docker compose

```bash
docker compose up -d orders-db orders
```

Reachable through nginx at `/api/orders/*` (see
[nginx/nginx.conf](../../nginx/nginx.conf)), not exposed on the host
directly — same pattern as catalog/inventory. Unlike those two, `/api/orders/cart`
and `/api/orders/checkout` are also reachable without a Firebase login (see
"Guest checkout" above); `/api/orders/orders` still requires one.

End-to-end smoke test against the real gateway with real Firebase-issued
tokens *and* the real (not mocked) Inventory service — registered-customer
checkout, insufficient-stock checkout, and the full guest-cookie flow:

```bash
docker compose up -d --build inventory-db inventory orders-db orders nginx
./scripts/verify-orders-gateway.sh
```

## Migrations

New migration after changing `src/orders/models.py`:

```bash
DATABASE_URL=postgresql+asyncpg://orders:orders@localhost:5435/orders \
  uv run alembic revision --autogenerate -m "describe the change"
```

Note: if a migration adds new `OrderStatus` members (the future saga
ticket), `ALTER TYPE order_status ADD VALUE ...` cannot run inside the same
transaction as other DDL in older Postgres — keep that migration to just the
`ADD VALUE` statement(s) if this is still a constraint on the Postgres
version in use at that time.
