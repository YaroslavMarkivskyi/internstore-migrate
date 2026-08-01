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
- Access tokens already issued remain valid until natural expiry (short TTL,
  target ≤5 min) — there is no per-request revocation check, consistent with
  AUTH-03's "no synchronous call per request" constraint.
- A revoked refresh token can no longer be used to mint new access tokens.

## Roles

| Role     | Notes                                             |
|----------|----------------------------------------------------|
| customer | Default role granted on registration.              |
| admin    | Never self-assignable; granted via Keycloak admin. |
