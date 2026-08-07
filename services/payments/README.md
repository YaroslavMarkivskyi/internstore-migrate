# payments

Dev-only payment simulation for the Temporal-orchestrated checkout saga
(STR-139). Not a domain service in the usual sense — it exists purely as an
activity target for `services/checkout-workflow`'s `CheckoutWorkflow`
(`charge_payment` / `refund_payment`), so checkout has an explicit,
independently retriable payment step to orchestrate. There is no real
payment gateway integration here; see "Failure simulation" below.

Same stack as [services/inventory](../inventory): Python/FastAPI/SQLAlchemy
(async)/Alembic, its own Postgres database, and the same internal-token
verification pattern (see [src/payments/auth.py](src/payments/auth.py)).
Unlike the other domain services, Payments has **no nginx route** — it's
only reachable from other containers on the compose network (the
checkout-workflow worker mints its own internal token via
`mint_internal_token`, the same pattern `ai-assistant`/`mcp-gateway` use for
their own internal-only call sites).

## Data model

- `Payment` — one row per charged order. `order_id` is a bare UUID
  referencing Orders' `Order.id` (no FK, no shared DB — same convention as
  every other cross-service reference in this codebase). The unique
  constraint on `order_id` is the idempotency key for `POST /charge`.
  `status` is `charged | refunded | failed`.

## Endpoints

Both require a valid `X-Internal-Token` (any role — Payments is only ever
called by the checkout-workflow worker, which always mints an `admin`-role
token for itself). Each handler calls a `check_permission()` stub (always
`True`) at the point a real OPA check will eventually go — placeholder
only, per STR-139's authorization note; no policy logic here.

- `POST /charge` — `{order_id, amount, payment_method}` →
  `{payment_id, status}`, 201. Idempotent via `order_id`: a retried/duplicate
  charge for the same `order_id` returns the existing row instead of
  charging twice (checked by lookup, and by catching the unique-constraint
  violation on a losing race).
- `POST /refund` — `{payment_id}` → `{status}`, 200. Idempotent via
  `payment_id`: refunding an already-refunded payment is a no-op that
  returns the current status. 404 on unknown `payment_id`.

## Failure simulation

No real Stripe/payment gateway integration in this ticket — `POST /charge`
simulates success or failure deterministically off the requested `amount`:
an amount whose two-decimal string form ends in
`Settings.payment_fail_on_amount_suffix` (default `"99"`, e.g. `19.99`)
returns `status: "failed"` instead of `"charged"`, so saga tests can force
the payment-failure/compensation path on demand without a real gateway.

## Local dev without Docker

```
cp .env.example .env   # DATABASE_URL, INTERNAL_TOKEN_SECRET
uv sync
uv run alembic upgrade head
uv run uvicorn payments.main:create_app --factory --reload
```

## Run tests

```
uv run pytest
```

Self-contained — uses an in-memory SQLite DB, no Postgres/Docker required.

## Via docker compose

```
docker compose up -d --build payments
```

Not routed through nginx (internal-only). Reachable from other containers
at `http://payments:8000`.

## Migrations

```
DATABASE_URL=postgresql+asyncpg://payments:payments@localhost:5432/payments \
  uv run alembic revision --autogenerate -m "..."
```
