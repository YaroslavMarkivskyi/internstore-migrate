# ADR 0004: Replace Keycloak with Firebase Authentication

- Status: Accepted
- Supersedes: [0001-replace-custom-identity-with-keycloak.md](0001-replace-custom-identity-with-keycloak.md)
- Date: 2026-08-13

## Context

ADR 0001 chose Keycloak as the self-hosted external identity provider,
specifically because it was "the most portable between on-prem/K8s and
AWS." This project's actual deployment target became GCP instead (see
STR-154/STR-180's Terraform + GKE work) — a GCP-native identity provider
(Firebase Authentication, GCP's rough equivalent to AWS Cognito) fits that
target better than a self-hosted IAM product does, and removes an entire
stateful service (Keycloak + its own Postgres instance) from the topology.

STR-155/STR-181 did this as a **surgical replacement**, confirmed
deliberately narrow in scope before implementing: only auth-backend's
external-token verification step changes (Keycloak JWKS → Firebase Admin
SDK's `verify_id_token`). Everything ADR 0001 established about the rest
of the architecture is unchanged and this ADR does not reopen it:

- The Gateway (auth-backend) still does authentication **offloading** —
  the only component that talks to the identity provider — and still
  mints a short-lived **internal** HS256 token for downstream services.
- Internal services still validate the internal token locally and never
  call the identity provider per request.
- Guest sessions (Redis-backed) are unrelated to either provider and
  untouched.
- OPA policies (STR-140/143) are keyed on internal-token claims, not the
  external provider's token shape, and are unaffected.

STR-192 then removed Keycloak itself (the container, its Postgres
instance, and all GCP/local-dev infrastructure for it) once the code no
longer verified anything it issued, and added the Firebase Auth emulator
for local dev in its place.

## Decision

Use **Firebase Authentication** as the external identity provider,
replacing Keycloak.

### Options considered (at STR-155 time)

| Option | Verdict | Why |
|---|---|---|
| Firebase Authentication | **Chosen** | GCP-native (same project, same IAM story via Workload Identity — no service-account JSON key to manage), AWS Cognito's rough equivalent for a GCP target. Admin SDK's `verify_id_token(check_revoked=True)` is a close match for the revocation check ADR 0001/AUTH-05 already required. |
| Keep Keycloak, deploy to GKE | Rejected | ADR 0001's own "AWS deployment plan" already flagged self-hosted-in-EKS as more ops burden than a managed alternative "if Keycloak's operational cost... turns out not to be worth it" — GKE is the same trade-off. One fewer stateful service (and its own Postgres instance) to operate is a real simplification for a demo-scale project. |
| Ory (Kratos/Hydra) | Not reconsidered | Already rejected in ADR 0001 for splitting identity/OAuth2 into two services; that reasoning doesn't change with the deployment target. |

## Architecture

```
Browser/Client
   │  1. Sign in via Firebase JS SDK (frontend, not built in this repo yet
   │     — see "Frontend" below)
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
   │     committed key file). check_revoked's revocation lookup replaces
   │     the old Keycloak-introspection call (auth/revocation.py, retired)
   │     as one step instead of two, and fails closed the same way: an
   │     unreachable Firebase raises rather than being swallowed.
   │  5. mints short-lived (≤60s) internal token (HS256, shared secret) —
   │     unchanged from ADR 0001
   ▼
Internal services
      6. validate internal token locally (HMAC) — no call to Firebase or
         the Gateway, unchanged from ADR 0001
```

### Roles: Firebase custom claims, not realm roles

Keycloak's `realm_access.roles` → Firebase custom claims
(`{"role": "customer" | "admin"}`, set via `set_custom_user_claims`).
Firebase has no realm-import-style default role composite, so there's no
direct equivalent of "customer is automatically granted on
self-registration" — an admin-side script
(`scripts/seed-firebase-users.py` for local dev; STR-181 flagged the real
GCP project's equivalent as a follow-up, not built yet) sets the claim
explicitly instead.

## Local development

`docker compose up -d` starts:

- `firebase-emulator` — Firebase Auth emulator, local-dev-only stand-in
  for a real Firebase project (see [firebase/README.md](../../firebase/README.md)
  for the image choice, the `host: 0.0.0.0` requirement, and two verified
  local-dev-only gaps: expired emulator tokens aren't rejected, and
  revocation checks race if triggered within the same wall-clock second
  as login)
- `redis` — Gateway sessions / guest carts (unchanged from ADR 0001)
- `auth-backend` — validates external tokens via the Firebase Admin SDK
  (redirected to the emulator via `FIREBASE_AUTH_EMULATOR_HOST`), mints
  internal tokens ([services/auth-backend](../../services/auth-backend))
- `nginx` — on-prem Gateway entry point, unchanged from ADR 0001
- domain services — unchanged from ADR 0001

[scripts/seed-firebase-users.py](../../scripts/seed-firebase-users.py)
creates the pre-seeded dev users (`customer@example.com`/
`admin@example.com`) that used to come from
`keycloak/realm-export.json` (removed by STR-192).
[scripts/test-auth-flows.sh](../../scripts/test-auth-flows.sh) exercises
AUTH-02 through AUTH-05 end-to-end against the compose stack for both
roles, same as ADR 0001's version did for Keycloak.

Keycloak's local docker-compose deployment is **not** kept around
alongside the emulator — STR-192 removed it entirely, everywhere (no
permanent dual-provider setup). k8s/overlays/local (kind) currently has no
Firebase emulator of its own either — a known, explicitly out-of-scope
gap for STR-192 (see that ticket's discussion) rather than something this
ADR resolves.

## GCP deployment

The GCP overlay (STR-154/STR-180's Terraform) uses a real Firebase
project via Application Default Credentials / Workload Identity — no
service-account JSON key committed anywhere, matching ADR 0001's original
"Secret Manager, not a key file" intent for credentials in general.
Keycloak's Cloud SQL instance, Workload Identity binding, and Secret
Manager secrets were removed by STR-192, bringing the demo environment's
Cloud SQL instance count from 11 back down to the original 10 (see
[terraform/gcp/environments/demo/README.md](../../terraform/gcp/environments/demo/README.md)).
Wiring the real Firebase project id into auth-backend's GCP config, and an
admin-side custom-claims script for that real project, are both flagged
by STR-181 as follow-ups — not done by STR-192 either, which stayed
scoped to *removing* Keycloak, not finishing Firebase's GCP-side setup.

## Frontend

Not built in this repo yet, flagged as a dependency (STR-181): the
frontend authenticates directly against Firebase via the Firebase JS SDK
and sends the resulting ID token to `/auth/verify`, the same shape it used
to send a Keycloak-issued token. `docker-compose.yml`'s
`VITE_KEYCLOAK_*` env vars are dead as of STR-192 (Keycloak is gone) but
left in place rather than deleted, so the frontend build doesn't break on
a missing env var before that migration lands.

## Consequences

- One fewer stateful service to operate (no more Keycloak + its own
  Postgres instance) — real simplification of ADR 0001's "one more
  stateful service" trade-off, at the cost of depending on a GCP-managed
  product instead of a portable self-hosted one. Acceptable since this
  project's actual deployment target is GCP, not "portable between
  on-prem/K8s and AWS" as ADR 0001 originally optimized for.
- Local dev now depends on the Firebase Auth emulator instead of a real
  Keycloak instance — faster/fully offline, but with two verified,
  documented gaps from real Firebase behavior (expiry not enforced,
  same-second revocation race) that don't apply to the GCP overlay's real
  Firebase project. See [firebase/README.md](../../firebase/README.md).
- Gateway and internal services now depend on a stable claim shape
  (Firebase custom claims `{"role": ...}`) instead of Keycloak's
  `realm_access.roles` — same category of coupling ADR 0001 already
  called out, just against a different provider's claim shape.
- k8s/overlays/local (kind) lost its working registered-user auth path
  (Keycloak) without gaining a replacement (no Firebase emulator wired
  into k8s) — an acknowledged regression for that one environment,
  tracked as a follow-up rather than resolved here. Guest checkout/catalog
  browsing are unaffected (no external token involved).
