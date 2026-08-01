# auth-backend

Validates Keycloak-issued JWTs and mints short-lived internal tokens for
downstream services. See
[docs/adr/0001-replace-custom-identity-with-keycloak.md](../../docs/adr/0001-replace-custom-identity-with-keycloak.md)
for the full design and [docs/requirements/AUTH.md](../../docs/requirements/AUTH.md)
for acceptance criteria.

## Endpoints

- `GET /health` — liveness check.
- `GET /me` — for manual/local testing: validates the `Authorization: Bearer`
  header and returns the decoded claims plus a minted internal token as JSON.
- `GET /auth/verify` — the endpoint fronted by nginx's `auth_request` (or an
  AWS ALB authorizer, see below). Validates the same way as `/me`, but
  communicates the result purely through status code and headers, since
  that's the contract both nginx and ALB expect:
  - `200` with `X-User-Id`, `X-User-Role`, `X-Internal-Token` response
    headers on a valid, non-revoked token.
  - `401` with no body otherwise (missing header, bad signature, expired,
    wrong `iss`/`aud`, or revoked).

## Why this is portable to AWS ALB, unchanged

`/auth/verify` has no nginx-specific code in it — no knowledge of
`auth_request`, no nginx variables, nothing beyond "read one header, return a
status and some headers." That's deliberate:

- **On-prem (nginx)**: nginx's `auth_request` directive calls `/auth/verify`
  as an internal subrequest, forwarding only the `Authorization` header, and
  copies `X-User-Id`/`X-User-Role`/`X-Internal-Token` from the response into
  the proxied request via `auth_request_set` (see
  [nginx/nginx.conf](../../nginx/nginx.conf)).
- **AWS (ALB)**: ALB's Lambda authorizer / OIDC integration follows the same
  shape — call an endpoint with the incoming `Authorization` header, get back
  an allow/deny plus headers to inject downstream. Pointing that
  configuration at this same `/auth/verify` endpoint (deployed as a
  container behind the ALB, or wrapped in a thin Lambda handler that calls
  the same `verifyExternalToken`/`mintInternalToken` functions) requires no
  changes to `src/auth/*`.

The only things that differ between topologies are deployment config (nginx
config vs. ALB listener rules) — never `src/`.

## Internal token trust boundary

Downstream services (e.g. [services/echo-service](../echo-service)) must
validate the internal token's signature and expiry themselves — they must
never trust `X-User-Id`/`X-User-Role` headers on their own, since anything on
the same network could set those. `createInternalTokenVerifier` in
[src/auth/internalToken.ts](src/auth/internalToken.ts) is the reusable piece
every domain service needs; see echo-service for a minimal example.

## Redis (not wired yet)

`REDIS_URL` is accepted and threaded through to
[src/auth/revocation.ts](src/auth/revocation.ts), which currently always
reports "not revoked". This is a placeholder for the `/logout` denylist
(AUTH-05) — real revocation checks land together with the logout endpoint.
