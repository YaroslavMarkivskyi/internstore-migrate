# AUTH-01…05 — Acceptance Criteria

These are not yet formally tracked elsewhere in this repo, so they're defined
here as the baseline the Firebase Authentication integration is validated
against (see
[docs/adr/0004-firebase-authentication.md](../adr/0004-firebase-authentication.md)).
Update this file if a different source of truth (Jira/Linear) supersedes it.

## AUTH-01 — Registration

- A visitor can register with email + password.
- On success the account gets the `customer` role by default (never `admin`)
  — set via a Firebase custom claim (`{"role": "customer"}`), not a
  default role composite (Firebase has no realm-import-style default role
  assignment — see ADR 0004's "Roles" section).
- Duplicate email is rejected with a clear error, no account is created.
- Password must satisfy Firebase Authentication's own minimum password
  policy (min length 6 by default).

## AUTH-02 — Login

- A registered user can log in with email + password and receives an ID
  token (JWT) and refresh token from Firebase.
- The ID token's custom claims contain the user's role (`{"role": "customer"
  | "admin"}`).
- Invalid credentials are rejected without revealing whether the email exists.

## AUTH-03 — Gateway token exchange

- The Gateway accepts the Firebase-issued ID token on inbound requests,
  validates it via the Firebase Admin SDK's `verify_id_token` (no separate
  synchronous call back to Firebase for signature/`exp`/`iss`/`aud`
  validation — Firebase's signing certs are cached in-process).
- On success, the Gateway mints a short-lived (≤60s) internal token (HMAC
  signed, `HS256`) carrying `sub`, `role`, and `exp`, for internal services to
  trust without re-validating against Firebase.
- Internal services validate the internal token locally using the shared HMAC
  secret and never call Firebase.

## AUTH-04 — Change password

- An authenticated user can change their own password given the current
  password.
- Changing the password does not require admin intervention.
- After a successful change, the user can log in with the new password and
  the old password no longer works.

## AUTH-05 — Logout / revocation

- Revoking a user's tokens (`revoke_refresh_tokens`, Admin SDK — logout
  itself is client-side-only under Firebase; see ADR 0004) invalidates
  their previously issued refresh tokens.
- A revoked refresh token can no longer be used to mint new ID tokens.
- ID tokens already issued are checked on every `/auth/verify` call via
  `verify_id_token(token, check_revoked=True)`, so a revoked token is
  rejected immediately rather than remaining valid until its own `exp`. This
  supersedes the original "no per-request revocation check" design —
  AUTH-03's "no synchronous call back to the provider per request"
  constraint still applies to signature/`exp`/`iss`/`aud` validation, which
  stays local, but no longer to revocation status.
- `check_revoked=True` is folded into the same `verify_id_token` call and
  has no separate cache layer — every call does its own lookup. A network
  failure during that lookup (Firebase unreachable or erroring) fails
  closed: the token is treated as revoked.

## Local-dev-only caveat (Firebase Auth emulator)

Verified directly, not assumed (see
[firebase/README.md](../../firebase/README.md)): against the local Firebase
Auth emulator specifically, `check_revoked=True` correctly enforces AUTH-05
above (revocation works, verified end-to-end), but **`exp` is not
enforced** — an expired emulator-issued token is still accepted. This is a
known emulator-only gap, not a violation of AUTH-03; real Firebase (used by
the GCP overlay) enforces `exp` normally.

## Roles

| Role     | Notes                                             |
|----------|----------------------------------------------------|
| customer | Default role granted on registration.              |
| admin    | Never self-assignable; granted via an admin-side script calling Firebase Admin SDK's `set_custom_user_claims` (`scripts/seed-firebase-users.py` for local dev). |
