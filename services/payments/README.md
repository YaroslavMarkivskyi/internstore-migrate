# payments

Dev-only payment simulation for the Temporal-orchestrated checkout saga
(STR-139). Not a domain service in the usual sense — it exists purely as an
activity target for `services/checkout-workflow`'s `CheckoutWorkflow`
(`charge_payment` / `refund_payment`), so checkout has an explicit,
independently retriable payment step to orchestrate. There is no real
payment gateway integration here; see "Failure simulation" below.

Same stack as [services/inventory](../inventory): Python/FastAPI/SQLAlchemy
(async)/Alembic, its own Postgres database. Unlike the other domain
services, Payments has **no nginx Gateway route** — it's only ever called
by the checkout-workflow worker, over the compose network (it mints its
own internal token via `mint_internal_token`, the same pattern
`ai-assistant`/`mcp-gateway` use for their own internal-only call sites).

## Data model

- `Payment` — one row per charged order. `order_id` is a bare UUID
  referencing Orders' `Order.id` (no FK, no shared DB — same convention as
  every other cross-service reference in this codebase). The unique
  constraint on `order_id` is the idempotency key for `POST /charge`.
  `status` is `charged | refunded | failed`.

## Endpoints

Every route is admin-only, no browser-facing endpoint at all — Payments is
only ever called by the checkout-workflow worker, which mints an
`admin`-role internal token for itself. None of this is enforced in this
service's own Python anymore: **payments-gate** (nginx, `auth_request`)
sits in front of it, occupying the network-facing port (`:8000`)
checkout-workflow's `PAYMENTS_BASE_URL` still calls; only `/health` passes
straight through, everything else goes through **payments-verify**
([services/internal-gate](../internal-gate), the same generic image
catalog/security use, parameterized by `OPA_PACKAGE=payments`) which
translates **payments-opa**'s decision
([policies/payments.rego](../../policies/payments.rego)) into the HTTP
status/headers `auth_request` needs. See
[nginx/internal-gate/payments.conf](../../nginx/internal-gate/payments.conf)
and [scripts/verify-payments-gate.sh](../../scripts/verify-payments-gate.sh).

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
cp .env.example .env   # DATABASE_URL
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
docker compose up -d --build payments payments-opa payments-verify payments-gate payments-db
```

Not routed through the external Gateway (internal-only). Reachable from
other containers at `http://payments:8000`, gated by payments-gate/
payments-verify/payments-opa as described above.

## Migrations

```
DATABASE_URL=postgresql+asyncpg://payments:payments@localhost:5432/payments \
  uv run alembic revision --autogenerate -m "..."
```
