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
  - `200` with the same headers (`X-User-Role: guest`) and a
    `Set-Cookie: is_guest_id=...` when no `Authorization` header is present
    **and** the request targets a guest-allowed path — see "Guest sessions"
    below.
  - `401` with no body otherwise (missing header, bad signature, expired,
    wrong `iss`/`aud`, revoked, or an unauthenticated request outside the
    guest-allowed paths).

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

## Guest sessions

[services/orders](../orders)'s cart (ORDC-01) and checkout (ORDC-02) need to
work for unauthenticated shoppers, not just Keycloak-registered customers —
there was no pre-existing session mechanism for this in the repo, so
`/auth/verify` gained one fallback branch (see
[src/auth/guestSession.ts](src/auth/guestSession.ts) and the guest branch in
[src/index.ts](src/index.ts)):

- Only granted on paths under `/api/orders/cart` or `/api/orders/checkout`
  (nginx forwards the original request path as `X-Original-URI` — see
  [nginx/nginx.conf](../../nginx/nginx.conf)). Every other path still 401s
  with no `Authorization` header, exactly as before — in particular,
  `/api/orders/orders` (order history) is deliberately **not** guest-allowed:
  a guest can check out but must register/log in to see past orders.
- On first hit, mints a random `guest_id`, stores it in Redis
  (`guest_session:<guest_id>`, 7-day TTL, not refreshed on reuse) and returns
  it as an `is_guest_id` cookie (`HttpOnly`, `Secure`, `SameSite=Lax`).
- On a later hit with a still-valid cookie, reuses the same `guest_id` — same
  cart, same identity — without minting a new one.
- Either way, mints a normal internal token with `role: "guest"` and
  `sub: <guest_id>`, exactly like the customer/admin path. Downstream
  services (Orders, and now Inventory's `check-availability`, since it
  forwards the caller's token — see [services/orders/README.md](../orders/README.md))
  treat `guest` as a third valid role, not a special case.
- Redis errors here are not swallowed — they propagate into the same
  try/catch that already turns invalid/expired tokens into a `401`, so a
  Redis outage fails closed instead of minting an unpersisted identity.

## Redis

`REDIS_URL` is required (`requireEnv`, not optional) since guest sessions
depend on it. It's also threaded through to
[src/auth/revocation.ts](src/auth/revocation.ts), which currently always
reports "not revoked" — a placeholder for the `/logout` denylist (AUTH-05);
real revocation checks land together with the logout endpoint. The two
Redis usages are unrelated: guest sessions use a `guest_session:` key
prefix, revocation will use its own.
