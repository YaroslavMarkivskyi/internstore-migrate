# ADR 0004: Firebase Authentication as the external identity provider

- Status: Accepted
- Date: 2026-08-13

## Context

InternStore needs an external identity provider for registered users
(`customer`/`admin`), sitting behind a Gateway (auth-backend) that does
authentication **offloading** — it is the only component that talks to the
identity provider — and mints a short-lived **internal** HS256 token for
downstream services. This project's deployment target is GCP (Terraform +
GKE, STR-154/STR-180), so a GCP-native identity provider fits that target
better than a self-hosted IAM product: it removes an entire stateful
service (its own Postgres instance) from the topology and reuses the
project's existing GCP IAM story (Workload Identity, no service-account
JSON key to manage).

STR-155/STR-181 landed this as a **surgical** integration, confirmed
deliberately narrow in scope before implementing: only auth-backend's
external-token verification step is Firebase-specific.

- Internal services validate the internal token locally and never call the
  identity provider per request.
- Guest sessions (Redis-backed) are unrelated to the identity provider and
  untouched.
- OPA policies (STR-140/143) are keyed on internal-token claims, not the
  external provider's token shape, and are unaffected.

STR-192 then finished removing the self-hosted alternative that had been
running before this decision (its container, its own Postgres instance,
and all GCP/local-dev infrastructure for it), and added the Firebase Auth
emulator for local dev in its place.

## Decision

Use **Firebase Authentication** as the external identity provider.

### Options considered (at STR-155 time)

| Option | Verdict | Why |
|---|---|---|
| Firebase Authentication | **Chosen** | GCP-native (same project, same IAM story via Workload Identity — no service-account JSON key to manage). Admin SDK's `verify_id_token(check_revoked=True)` is a close match for the revocation check AUTH-05 requires. |
| Self-hosted IAM product on GKE | Rejected | Running a full IAM product's own Postgres instance and HA clustering is more ops burden than a managed alternative is worth for a demo-scale project. One fewer stateful service to operate is a real simplification. |
| Ory (Kratos/Hydra) | Rejected | Splits identity/OAuth2 into two services to run and reason about, for no benefit at InternStore's current scale. |

## Architecture

```
Browser/Client
   │  1. Sign in via Firebase JS SDK (frontend/src/services/firebase/client.ts)
   ▼
Firebase Authentication (project: per-environment)
   │  2. issues external ID token (JWT)
   ▼
Browser/Client
   │  3. sends external token as Bearer to Gateway (auth-backend)
   ▼
Gateway (auth-backend)
   │  4. verify_id_token(token, check_revoked=True) — Firebase Admin SDK,
   │     Application Default Credentials (Workload Identity in GCP, no
   │     committed key file). check_revoked does its own revocation lookup
   │     per call and fails closed: an unreachable Firebase raises rather
   │     than being swallowed.
   │  5. mints short-lived (≤60s) internal token (HS256, shared secret)
   ▼
Internal services
      6. validate internal token locally (HMAC) — no call to Firebase or
         the Gateway
```

### Roles: Firebase custom claims

Firebase custom claims (`{"role": "customer" | "admin"}`, set via
`set_custom_user_claims`) carry the role. Firebase has no realm-import-style
default role composite, so there's no built-in equivalent of "customer is
automatically granted on self-registration" — an admin-side script
(`scripts/seed-firebase-users.py` for local dev; the real GCP project's
equivalent is flagged as a follow-up, not built yet) sets the claim
explicitly instead.

## Local development

`docker compose up -d` starts:

- `firebase-emulator` — Firebase Auth emulator, local-dev-only stand-in
  for a real Firebase project (see [firebase/README.md](../../firebase/README.md)
  for the image choice, the `host: 0.0.0.0` requirement, and two verified
  local-dev-only gaps: expired emulator tokens aren't rejected, and
  revocation checks race if triggered within the same wall-clock second
  as login)
- `redis` — Gateway sessions / guest carts
- `auth-backend` — validates external tokens via the Firebase Admin SDK
  (redirected to the emulator via `FIREBASE_AUTH_EMULATOR_HOST`), mints
  internal tokens ([services/auth-backend](../../services/auth-backend))
- `nginx` — on-prem Gateway entry point
- `frontend` — authenticates directly against Firebase via the Firebase JS
  SDK ([frontend/src/services/firebase/client.ts](../../frontend/src/services/firebase/client.ts))
  and sends the resulting ID token to `/auth/verify`
- domain services

[scripts/seed-firebase-users.py](../../scripts/seed-firebase-users.py)
creates the pre-seeded dev users (`customer@example.com`/
`admin@example.com`).
[scripts/test-auth-flows.sh](../../scripts/test-auth-flows.sh) exercises
AUTH-02 through AUTH-05 end-to-end against the compose stack for both
roles.

k8s/overlays/local (kind) currently has no Firebase emulator of its own —
a known, explicitly out-of-scope gap rather than something this ADR
resolves.

## GCP deployment

The GCP overlay (STR-154/STR-180's Terraform) uses a real Firebase
project via Application Default Credentials / Workload Identity — no
service-account JSON key committed anywhere. Wiring the real Firebase
project id into auth-backend's GCP config, and an admin-side custom-claims
script for that real project, are both flagged as follow-ups — not built
yet.

## Consequences

- One fewer stateful service to operate than a self-hosted IAM product
  would need (no extra Postgres instance) — at the cost of depending on a
  GCP-managed product instead of a portable self-hosted one. Acceptable
  since this project's actual deployment target is GCP.
- Local dev depends on the Firebase Auth emulator — faster/fully offline,
  but with two verified, documented gaps from real Firebase behavior
  (expiry not enforced, same-second revocation race) that don't apply to
  the GCP overlay's real Firebase project. See
  [firebase/README.md](../../firebase/README.md).
- Gateway and internal services depend on a stable claim shape (Firebase
  custom claims `{"role": ...}`) — a claim-shape change is a breaking
  change for the Gateway's role-extraction logic.
- k8s/overlays/local (kind) has no working registered-user auth path (no
  Firebase emulator wired into k8s) — an acknowledged gap, tracked as a
  follow-up rather than resolved here. Guest checkout/catalog browsing are
  unaffected (no external token involved).
