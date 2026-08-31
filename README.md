# InternStore — Firebase Authentication

See [docs/adr/0004-firebase-authentication.md](docs/adr/0004-firebase-authentication.md)
for the decision and architecture.
Acceptance criteria: [docs/requirements/AUTH.md](docs/requirements/AUTH.md).

## Local setup

```bash
docker compose up -d
uv run scripts/seed-firebase-users.py
```

This starts the Firebase Auth emulator (`:9099`, local-dev-only — see
[firebase/README.md](firebase/README.md)), Redis (`:6379`), auth-backend
(`:3001` on the host → `:3000` in the container, also reachable through nginx), the domain services (Catalog,
Inventory, Orders, Telemetry, Security, Chat — each reachable only through
nginx, e.g. Catalog at `/api/catalog/*`) and their own Postgres DBs, and
nginx (`:8082` plain → redirects to `:8443` TLS; `:8082` because `:8080` is
a common local conflict — remap in [docker-compose.yml](docker-compose.yml)
if `:8443`/`:8082` are also taken on your machine).
`scripts/seed-firebase-users.py` creates the two seed users:

| Email | Password | Role |
|---|---|---|
| customer@example.com | Customer123 | customer |
| admin@example.com | Admin123456 | admin |

Wait for the emulator to report healthy, then run the end-to-end auth check:

```bash
./scripts/test-auth-flows.sh
```

To exercise the full gateway path (nginx → auth-backend → a domain service,
e.g. Catalog), including negative cases, internal-token isolation/TTL, and
the WebSocket proxy (~15-20s, briefly stops/restarts the Firebase emulator):

```bash
./scripts/verify-gateway.sh
```

## API Gateway (nginx + auth-backend)

The Gateway is split into two logically separate pieces that are brought up
together:

- [nginx/](nginx) — entry point for the on-prem topology: TLS termination,
  `auth_request` to auth-backend, and routing to the domain services
  (Catalog, Inventory, Orders, Telemetry, Security, Chat).
- [services/auth-backend](services/auth-backend) — Python/FastAPI service
  (same stack as every domain service) that validates Firebase-issued ID
  tokens via the Firebase Admin SDK and mints short-lived internal tokens
  for downstream services. nginx deliberately does *not* validate tokens
  itself: that logic lives here (see
  [services/auth-backend/README.md](services/auth-backend/README.md)).

Local dev without Docker (auth-backend only; nginx needs the other services
running to be useful):

```bash
cd services/auth-backend
cp .env.example .env
uv sync
uv run uvicorn auth_backend.main:create_app --factory --reload
```

## Domain services

First domain service split out of the monolith:

- [services/catalog](services/catalog) — categories and products
  (Python/FastAPI/SQLAlchemy/Alembic, its own Postgres DB, zero coupling to
  other domain services). Reachable through nginx at `/api/catalog/*`.
  Unlike the gateway pieces above, domain services going forward use this
  stack rather than TypeScript/Fastify — see the service's README for why.

## Event broker

Kafka (KRaft mode, single node) backs the choreographed Orders/Inventory
reservation saga and other cross-service events. Decision, topic list, and
connection details: [docs/adr/0002-event-broker-kafka.md](docs/adr/0002-event-broker-kafka.md)
and [docs/EVENT_BROKER.md](docs/EVENT_BROKER.md).

```bash
docker compose up -d kafka kafka-topic-init
./scripts/test-kafka-smoke.sh
```
