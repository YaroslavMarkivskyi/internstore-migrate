# InternStore — Identity migration to Keycloak

See [docs/adr/0001-replace-custom-identity-with-keycloak.md](docs/adr/0001-replace-custom-identity-with-keycloak.md)
for the decision and architecture. Acceptance criteria: [docs/requirements/AUTH.md](docs/requirements/AUTH.md).

## Local setup

```bash
docker compose up -d
```

This starts Keycloak (`:8081`, admin console at `/admin`, login `admin`/`admin`),
its Postgres DB, Redis (`:6379`), auth-backend (`:3000`, also reachable
through nginx), the echo-service stub, the catalog service and its own
Postgres DB (reachable only through nginx at `/api/catalog/*`), and nginx
(`:8082` plain → redirects to `:8443` TLS; `:8082` because `:8080` is a
common local conflict — remap in [docker-compose.yml](docker-compose.yml) if
`:8443`/`:8082` are also taken on your machine). Keycloak imports the
`internstore` realm from
[keycloak/realm-export.json](keycloak/realm-export.json) on first boot,
including two seed users:

| Email | Password | Role |
|---|---|---|
| customer@example.com | Customer123 | customer |
| admin@example.com | Admin123456 | admin |

Wait for Keycloak to report healthy, then run the end-to-end auth check:

```bash
./scripts/test-auth-flows.sh
```

To exercise the full gateway path (nginx → auth-backend → echo-service),
including negative cases, internal-token isolation/TTL, JWKS-cache
resilience, and the WebSocket proxy (~90s, briefly stops/restarts Keycloak):

```bash
./scripts/verify-gateway.sh
```

## API Gateway (nginx + auth-backend)

The Gateway is split into two logically separate pieces that are brought up
together:

- [nginx/](nginx) — entry point for the on-prem topology: TLS termination,
  `auth_request` to auth-backend, routing to domain services (currently just
  the echo-service stub), and a WebSocket proxy location reserved for the
  future Chat service.
- [services/auth-backend](services/auth-backend) — TypeScript/Fastify
  service that validates Keycloak-issued JWTs against the realm's JWKS
  endpoint and mints short-lived internal tokens for downstream services.
  nginx deliberately does *not* validate JWTs itself: that logic lives here
  so it's portable, unchanged, to an AWS ALB topology later (see
  [services/auth-backend/README.md](services/auth-backend/README.md)).

Local dev without Docker (auth-backend only; nginx needs the other services
running to be useful):

```bash
cd services/auth-backend
cp .env.example .env
pnpm install
pnpm dev
```

## Domain services

First domain service split out of the monolith:

- [services/catalog](services/catalog) — categories and products
  (Python/FastAPI/SQLAlchemy/Alembic, its own Postgres DB, zero coupling to
  other domain services). Reachable through nginx at `/api/catalog/*`.
  Unlike the gateway pieces above, domain services going forward use this
  stack rather than TypeScript/Fastify — see the service's README for why.
