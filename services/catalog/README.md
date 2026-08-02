# catalog

Categories and products for InternStore. First domain service split out of
the monolith, originally with zero coupling to other domain services; it
now publishes `ProductThresholdUpdated` on `catalog-events` (transactional
outbox, same pattern as Inventory/Orders) so Telemetry can cache each
product's temperature threshold locally — see
[services/telemetry](../telemetry). Its own Postgres database, no shared
tables with any other service.

Python/FastAPI/SQLAlchemy(async)/Alembic — first domain service on this
stack, and now the same stack [services/auth-backend](../auth-backend) uses
too (STR-120 ported the gateway layer onto it, and removed the
`echo-service` placeholder now that real domain services exist).

## Endpoints

- `GET /health` — liveness check.
- `GET /categories` — public, list categories.
- `POST /categories` — admin-only. Body: `{"name": "..."}`, 3-15 characters,
  unique. 401 with no/invalid internal token, 403 for a non-admin token, 409
  on duplicate name.
- `GET /products` — public, list products.
- `GET /products/{id}` — public, product details. 404 if not found.
- `POST /products` — admin-only. Body: `{"name", "price", "category_id"}`
  required (`name` 2-250 chars, `price` > 0); `description` (≤500 chars),
  `min_temperature`, `max_temperature` optional. 422 on an unknown
  `category_id`.
- `PATCH /products/{id}` — admin-only. Body: any subset of
  `name`/`price`/`category_id`/`description`/`min_temperature`/`max_temperature`
  (partial update — only fields present are applied). 404 if not found, 422
  on an unknown `category_id`. If `min_temperature` or `max_temperature`
  actually change, stages `ProductThresholdUpdated` on the outbox in the
  same transaction as the update.

Search (SEARCH-01/02), photo upload (PROD-06/07), and filtering/sorting
(FILT-01/03) are explicitly out of scope for this cut.

## Kafka

Producer only (no consumers): `ProductThresholdUpdated` on `catalog-events`,
staged via the transactional outbox
([src/catalog/outbox.py](src/catalog/outbox.py) +
[src/catalog/outbox_worker.py](src/catalog/outbox_worker.py)) in the same
commit as the `PATCH /products/{id}` update that changed a temperature
field — same pattern as Inventory/Orders' outbox. Telemetry is the only
consumer today (see [services/telemetry](../telemetry)).

## Auth

Every write endpoint validates the `X-Internal-Token` header locally — HMAC
(HS256) signature, `iss`, `exp` — against the same shared secret
`auth-backend` mints with (`INTERNAL_TOKEN_SECRET`). This service never
trusts `X-User-Id`/`X-User-Role` headers directly and never calls back to
Keycloak or auth-backend. See
[src/catalog/auth.py](src/catalog/auth.py), which mirrors
`services/auth-backend/src/auth_backend/auth/internal_token.py`.

## Local dev without Docker

```bash
cd services/catalog
cp .env.example .env   # point DATABASE_URL at a local Postgres
uv sync
uv run alembic upgrade head
uv run uvicorn catalog.main:create_app --factory --reload
```

Run tests (self-contained, in-memory SQLite, no DB needed):

```bash
uv run pytest
```

## Via docker compose

```bash
docker compose up -d catalog-db catalog
```

Reachable through nginx at `/api/catalog/*` (see [nginx/nginx.conf](../../nginx/nginx.conf)),
not exposed on the host directly — same pattern as every other domain service.

## Migrations

New migration after changing `src/catalog/models.py`:

```bash
DATABASE_URL=postgresql+asyncpg://catalog:catalog@localhost:5433/catalog \
  uv run alembic revision --autogenerate -m "describe the change"
```
