# AUTH-01…05 — Acceptance Criteria

These are not yet formally tracked elsewhere in this repo, so they're defined
here as the baseline the Keycloak integration is validated against (see
[docs/adr/0001-replace-custom-identity-with-keycloak.md](../adr/0001-replace-custom-identity-with-keycloak.md)).
Update this file if a different source of truth (Jira/Linear) supersedes it.

## AUTH-01 — Registration

- A visitor can register with email + password.
- On success the account gets the `customer` role by default (never `admin`).
- Duplicate email is rejected with a clear error, no account is created.
- Password must satisfy the realm's password policy (min length 8, upper +
  lower + digit).

## AUTH-02 — Login

- A registered user can log in with email + password and receives an access
  token (JWT) and refresh token from Keycloak.
- The access token's `realm_access.roles` contains the user's role
  (`customer` or `admin`).
- Invalid credentials are rejected without revealing whether the email exists.

## AUTH-03 — Gateway token exchange

- The Gateway accepts the Keycloak-issued access token on inbound requests,
  validates its signature against Keycloak's JWKS endpoint (no synchronous
  call back to Keycloak per request), and checks `exp`/`iss`/`aud`.
- On success, the Gateway mints a short-lived (≤60s) internal token (HMAC
  signed, `HS256`) carrying `sub`, `role`, and `exp`, for internal services to
  trust without re-validating against Keycloak.
- Internal services validate the internal token locally using the shared HMAC
  secret and never call Keycloak.

## AUTH-04 — Change password

- An authenticated user can change their own password given the current
  password.
- Changing the password does not require admin intervention.
- After a successful change, the user can log in with the new password and
  the old password no longer works.

## AUTH-05 — Logout / revocation

- A logout request revokes the refresh token (and, per Keycloak session
  semantics, the associated session) at Keycloak.
- A revoked refresh token can no longer be used to mint new access tokens.
- Access tokens already issued are checked on every `/auth/verify` call via
  Keycloak's token introspection endpoint (RFC 7662), so a revoked token is
  rejected immediately rather than remaining valid until its own `exp`. This
  supersedes the original "no per-request revocation check" design —
  AUTH-03's "no synchronous call back to Keycloak per request" constraint
  still applies to signature/`exp`/`iss`/`aud` validation, which stays local
  via JWKS, but no longer to revocation status.
- Introspection results are cached for up to 30s per token, bounding the
  worst-case revocation-propagation window to that cache TTL instead of the
  access token's full remaining lifetime. Introspection failures (Keycloak
  unreachable or erroring) fail closed: the token is treated as revoked.

## Roles

| Role     | Notes                                             |
|----------|----------------------------------------------------|
| customer | Default role granted on registration.              |
| admin    | Never self-assignable; granted via Keycloak admin. |
