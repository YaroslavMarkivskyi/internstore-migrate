# InternStore — Identity migration to Keycloak

See [docs/adr/0001-replace-custom-identity-with-keycloak.md](docs/adr/0001-replace-custom-identity-with-keycloak.md)
for the decision and architecture. Acceptance criteria: [docs/requirements/AUTH.md](docs/requirements/AUTH.md).

## Local setup

```bash
docker compose up -d
```

This starts Keycloak (`:8081`, admin console at `/admin`, login `admin`/`admin`),
its Postgres DB, Redis (`:6379`), and the Gateway (`:3000`). Keycloak imports
the `internstore` realm from [keycloak/realm-export.json](keycloak/realm-export.json)
on first boot, including two seed users:

| Email | Password | Role |
|---|---|---|
| customer@example.com | Customer123 | customer |
| admin@example.com | Admin123456 | admin |

Wait for Keycloak to report healthy, then run the end-to-end auth check:

```bash
./scripts/test-auth-flows.sh
```

## Gateway

TypeScript/Fastify service in [services/gateway](services/gateway). Validates
Keycloak-issued JWTs against the realm's JWKS endpoint and mints short-lived
internal tokens for downstream services (see ADR for why). Local dev without
Docker:

```bash
cd services/gateway
cp .env.example .env
pnpm install
pnpm dev
```
