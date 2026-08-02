# ADR 0001: Replace custom Identity service with Keycloak

- Status: Accepted
- Supersedes: draft ADR for a custom-built Identity service (never merged)
- Date: 2026-08-01

## Context

The original plan was to build a custom Identity microservice (own user
store, password hashing, token issuance) for InternStore. That plan is
rejected in favor of a proven IAM product ("don't roll your own auth"):

- Custom crypto/session code has a real track record of timing attacks, key
  rotation mistakes, and subtle OIDC/OAuth2 non-compliance — all high-cost to
  get wrong in an auth system specifically.
- A production-grade product gets us registration, login, password policy,
  MFA-readiness, and revocation without re-implementing them.
- Integrating a real IAM product into a microservice architecture is itself
  the skill being exercised here, not writing another JWT library.

This does not change the rest of the previously agreed architecture:

- The Gateway still does authentication **offloading**: it is the only
  component that talks to the auth provider's token endpoint/JWKS, and it
  issues a short-lived **internal** token for downstream services.
- Internal services validate the internal token locally (HMAC) and never
  call the auth provider per request.
- Redis is still used for Gateway sessions / guest carts — unrelated to
  Keycloak's own session store, which only covers Keycloak-authenticated
  sessions.

## Decision

Use **Keycloak** as the auth provider.

### Options considered

| Option  | Verdict | Why |
|---------|---------|-----|
| Keycloak | **Chosen** | Self-hosted, most portable between on-prem/K8s and AWS (runs the same in EKS as anywhere else, or via AWS-managed alternatives if that changes later). Mature OIDC/OAuth2 implementation, realm/role model maps directly onto `customer`/`admin`. |
| Ory (Kratos/Hydra) | Rejected for now | Lighter and more cloud-native, but splits identity (Kratos) and OAuth2 (Hydra) into two services to run and reason about, for no benefit at InternStore's current scale. Worth revisiting if operational simplicity becomes the bottleneck instead of features. |
| Auth0 | Rejected | SaaS-only. Doesn't fit the on-prem/K8s deployment target; introduces an external hosted dependency and per-MAU billing we don't need for a learning-scale project. |

## Architecture

```
Browser/Client
   │  1. Authorization Code + PKCE login
   ▼
Keycloak (realm: internstore)
   │  2. issues external access token (JWT, RS256, signed by realm key)
   ▼
Browser/Client
   │  3. sends external token as Bearer to Gateway
   ▼
Gateway
   │  4. validates external token signature via Keycloak JWKS
   │     (cached in-process; refetched only on unknown `kid`, not per request)
   │  5. mints short-lived (≤60s) internal token (HS256, shared secret)
   ▼
Internal services
      6. validate internal token locally (HMAC) — no call to Keycloak or Gateway
```

### Internal token: minted by the Gateway, not a Keycloak token exchange

Keycloak supports the OAuth2 Token Exchange extension, but it requires
enabling a preview feature and a round trip to Keycloak per exchange — the
opposite of "no synchronous call per request." Instead, the Gateway mints
the internal token itself once it has already validated the external token
locally: it re-signs the claims it needs (`sub`, `role`, short `exp`) with an
HMAC secret shared only among internal services. This keeps the "validate
once at the edge, trust internally" property from the original design.

### Roles

Keycloak realm roles `customer` and `admin`. `customer` is part of the
realm's default role composite, so self-registration grants it
automatically; `admin` is never in the defaults and is only assignable via
the Keycloak admin console/API. See
[docs/requirements/AUTH.md](../requirements/AUTH.md) for the full AUTH-01…05
acceptance criteria this was validated against.

## Local development

`docker compose up -d` starts:

- `keycloak-db` (Postgres) — Keycloak's own store
- `keycloak` — imports [keycloak/realm-export.json](../../keycloak/realm-export.json)
  on boot (`start-dev --import-realm`), pre-seeded with one `customer` and
  one `admin` test user
- `redis` — Gateway sessions / guest carts (unchanged from prior design)
- `auth-backend` — validates external tokens via JWKS, mints internal tokens
  ([services/auth-backend](../../services/auth-backend))
- `nginx` — on-prem Gateway entry point: TLS termination, `auth_request` to
  `auth-backend`, routing to domain services
  ([nginx](../../nginx))
- domain services — Catalog, Inventory, Orders, Telemetry, Security, and
  Chat are all reachable through nginx once the stack is up (e.g. Catalog
  at `/api/catalog/*`); any of them exercises the end-to-end auth path,
  there's no dedicated stub service anymore (see STR-120, which removed
  the original `echo-service` placeholder now that real domain services
  exist)

[scripts/test-auth-flows.sh](../../scripts/test-auth-flows.sh) exercises
AUTH-02 through AUTH-05 end-to-end against the compose stack for both roles.

## AWS deployment plan

Two viable paths, not yet decided between — tracked as follow-up, not
blocking this ADR:

1. **Self-hosted in EKS**: same container image as local dev, RDS Postgres
   instead of the compose Postgres, Keycloak's clustering (Infinispan/JGroups
   over the pod network) for multi-replica HA. Full control, more ops burden.
2. **AWS-managed alternative** (e.g. Amazon Cognito) as a drop-in behind the
   same Gateway JWKS-validation contract, if Keycloak's operational cost in
   EKS turns out not to be worth it. Would require re-mapping Cognito's
   group/claim model onto `customer`/`admin` but doesn't change the Gateway
   or internal-token design at all, since that boundary already only
   depends on "a JWKS endpoint and a realm role claim."

Default recommendation: start with (1) self-hosted in EKS, since it's what's
running in docker-compose and keeps dev/prod parity; revisit (2) only if
running Keycloak becomes an operational burden.

## Consequences

- One more stateful service to operate (Keycloak + its Postgres), instead of
  our own Identity service's database. Net operational surface is similar;
  what changes is that the hard parts (crypto, OIDC compliance, revocation)
  are no longer our code to maintain.
- Gateway and internal services depend on a stable claim shape
  (`realm_access.roles`) from Keycloak — a Keycloak realm/role rename is now
  a breaking change for the Gateway's role-extraction logic.
- True self-service registration (AUTH-01) is a Keycloak-hosted browser
  form, not a JSON API — automated end-to-end testing of it needs a browser
  driver (e.g. Playwright) or is verified manually; it isn't covered by
  `test-auth-flows.sh`.
