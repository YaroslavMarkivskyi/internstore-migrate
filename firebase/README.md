# Firebase Auth emulator (local dev only)

STR-181 swapped auth-backend's external token verification from Keycloak to
the Firebase Admin SDK. This directory is what makes that verifiable
*locally* without a real Firebase project: `docker-compose.yml`'s
`firebase-emulator` service runs the Firebase Local Emulator Suite's Auth
emulator only, and `auth-backend` talks to it via
`FIREBASE_AUTH_EMULATOR_HOST` — `firebase_admin` redirects every call there
automatically once that env var is set, no code branching required.

This emulator setup is **local-dev-only**, same category as this repo's
other dev-only infra stand-ins (e.g. MinIO standing in for GCS, Mailpit
standing in for a real SMTP relay). The GCP overlay uses a real Firebase
project via Application Default Credentials/Workload Identity — nothing
here applies there.

## Image choice (measured, not assumed)

Two options were compared by actually timing them, not guessing:

- `node:20-alpine` + `npx firebase-tools emulators:start` on every
  container start: **~27s** just for `npm install -g firebase-tools`
  (measured cold), repeated on *every* `docker compose up`/restart unless a
  node_modules volume is added — slow and non-reproducible (whatever's
  latest on npm at boot time).
- `andreysenov/firebase-tools:latest` (firebase-tools pinned into the
  image, currently CLI 15.26.0): a one-time `docker pull` (~20s, cached by
  Docker afterwards) and the emulator is ready in ~10s on every subsequent
  start.

Went with the pinned image for faster, reproducible local startup.

## `host: 0.0.0.0` is required, not optional

The Firebase emulator binds to `127.0.0.1` by default. That's the
container's *own* loopback — Docker's port mapping (`-p 9099:9099`)
forwards to the container's external interface, not its loopback, so a
default-bound emulator is completely unreachable from the host or from
other containers (`auth-backend` included) despite `docker ps` showing the
port as published. Confirmed by testing both ways while building this:
default binding → connection reset on every host-side request; explicit
`"host": "0.0.0.0"` in `firebase.json` (this directory) → works. This is a
well-known Firebase-emulator-in-Docker gotcha, not specific to this repo.

## No Emulator UI

`firebase.json` deliberately doesn't enable the UI (:4000). It needs its
own zip download (`ui-v1.15.0.zip` from `storage.googleapis.com`) on every
cold start — there's no image-side cache for it, unlike the CLI itself —
and that download flaked while building this, taking the whole
`firebase emulators:start` process down with it (including the Auth
emulator API, the one thing `auth-backend` actually depends on). A debug
UI isn't worth being a single point of failure for local dev bootstrap.
Use the REST API directly (`scripts/seed-firebase-users.py`,
`identitytoolkit.googleapis.com/v1/accounts:signInWithPassword` — see the
saga/verify scripts' `login()` functions) instead of the UI.

## Known gap: expired tokens are NOT rejected by the emulator

Verified directly, not assumed (this one *isn't* prod-equivalent, unlike
revocation below): `firebase_admin.auth.verify_id_token()` does not reject
a token whose `exp` claim is in the past when the SDK is talking to the
Auth emulator. The emulator issues unsigned tokens (`alg: none`), and the
SDK's emulator-mode path skips the standard `exp`/`iat` validation it runs
against a real, signed Firebase token — confirmed by hand-editing an
emulator token's `exp` into the past and calling `verify_id_token(token,
check_revoked=True)`: it returns successfully instead of raising
`ExpiredIdTokenError`. `aud` (wrong Firebase project) mismatches and
malformed payloads *are* still rejected — this gap is specific to time-based
expiry.

Local-dev-only, same as everything else on this page: real Firebase (the
GCP overlay) validates `exp` normally, this is not a production auth
bypass. `scripts/verify-gateway.sh` and `scripts/test-auth-flows.sh` don't
assert an expired-token rejection for exactly this reason — asserting it
would just be testing the emulator's own known limitation, not
auth-backend's behavior.

## Revocation check — verified, not assumed

STR-181 flagged `check_revoked=True`'s behavior against the emulator as
unverified. Tested directly: `auth.revoke_refresh_tokens(uid)` against the
emulator updates `tokens_valid_after_timestamp` exactly like real Firebase,
and `verify_id_token(token, check_revoked=True)` correctly raises
`RevokedIdTokenError` for a token minted before that revocation. **No gap**
— the emulator's revocation semantics match production here, so
auth-backend's fail-closed revocation check is exercised faithfully in
local dev too.

## Seeding dev users

See [scripts/seed-firebase-users.py](../scripts/seed-firebase-users.py) —
run after `docker compose up -d` to create the `customer@example.com` /
`admin@example.com` test users (with `{"role": ...}` custom claims) this
project's verification scripts assume exist.
