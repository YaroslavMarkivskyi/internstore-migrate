# security

Fingerprint/NFC warehouse access control for InternStore. Sixth domain
service, and the only one that's pure REST — no Kafka, no outbox. Access
control is synchronous by nature: a door open/close decision can't wait on
eventual consistency, so every auth attempt is written straight to
Security's own DB in the same request.

Covers EP-08 (Security) and the fingerprint/NFC scope of EP-09 (Security
and environmental warehouse control system); temperature/humidity
monitoring is [Telemetry](../telemetry)'s.

Same stack as [services/telemetry](../telemetry):
Python/FastAPI/SQLAlchemy(async)/Alembic, its own Postgres database with
zero shared tables. Unlike Telemetry, this service's own FastAPI code
carries no internal-token verification at all anymore — see "Auth flow"
below.

## Data model

- `User` — one row per registered employee (fingerprint, AS608) or
  supplier (NFC, MFRC-522); `auth_type` discriminates which credential
  shape applies. `credential` is the fingerprint template (base64) or the
  raw NFC card UID string — never returned by any endpoint.
  `warehouse_ids` is what admins read/write via `POST`/`PATCH /users`.
- `Warehouse` — `id` is always Inventory's `Stock.id`; there's no
  "warehouse created" event to sync from, so a row is lazily upserted the
  first time an auth attempt names a given id (see
  [src/security/warehouses.py](src/security/warehouses.py)) — same pattern
  as Telemetry's `stores.get_or_create_store`.
- `AccessRule` — normalized `{user_id, warehouse_id}` join, composite PK.
  This is what `POST /auth/*` actually joins against; it's kept in sync
  with `User.warehouse_ids` by the `/users` routes
  (`_sync_access_rules`) rather than independently editable.
- `VisitLog` — one row per auth attempt, success or failure. `user_id` is
  null only when the credential matched no user at all (unknown
  fingerprint template / card UID); every other denial still resolves a
  `user_id`. `video_url` is always set, pointing at mock-camera's fixed
  clip.

## Auth flow

`POST /auth/fingerprint` and `POST /auth/nfc` have no auth dependency —
they're called directly by the hardware simulator (a fingerprint reader or
an NFC reader), not through a logged-in admin session. Same trust model as
Telemetry's `POST /measurements`: open within the docker network, not
routed through the Gateway.

`/users`, `/visit-log`, and `/warehouses` are admin-only, including their
own `GET` routes — unlike catalog's public-read/admin-write split, this
service's split is path-based, not method-based. None of this is enforced
in this service's own Python anymore: **security-gate** (nginx,
`auth_request`) sits in front of it, occupying the network-facing port
(`:8000`) every other service still calls `security:8000` at; `/auth/*`
and `/health` pass straight through, everything else goes through
**security-verify** ([services/internal-gate](../internal-gate), the same
generic image catalog uses, parameterized by `OPA_PACKAGE=security`) which
translates **security-opa**'s decision
([policies/security.rego](../../policies/security.rego)) into the HTTP
status/headers `auth_request` needs. See
[nginx/internal-gate/security.conf](../../nginx/internal-gate/security.conf)
for the full wiring and
[scripts/verify-security-gate.sh](../../scripts/verify-security-gate.sh)
for the live end-to-end check — same pattern as
[services/catalog's own Auth section](../catalog/README.md#auth), which
this mirrors.

The `security` container itself binds `127.0.0.1` only (`HOST=127.0.0.1`)
— unreachable from outside this pod's shared network namespace even if
something guesses its real port.

Each attempt:

1. Lazily creates the `Warehouse` row if `warehouse_id` is new.
2. Looks up a `User` by `{auth_type, credential}`. No match ->
   `denial_reason: "unknown credential"`, `user_id: null`.
3. If the user is `is_active: false` -> `denial_reason: "inactive user"`.
4. If there's no `AccessRule` row for `{user_id, warehouse_id}` ->
   `denial_reason: "no access to this warehouse"`.
5. Otherwise `allowed: true`.

Every attempt — allowed or denied — writes a `VisitLog` row with a
`video_url` built from `CAMERA_BASE_URL`.

## Hardware simulation gaps (dev-only, accepted)

- Fingerprint matching is a plain string comparison against the stored
  `credential` — the real AS608 sensor's biometric template matching
  (minutiae extraction, similarity scoring) isn't replicated.
- NFC card UID matching is an exact string match — the real MFRC-522
  protocol (ISO 14443A anticollision, UID read) isn't replicated.
- `mock-camera` serves a single bundled 3-second test clip on any `GET`,
  regardless of path — real ESP32-CAM video capture isn't replicated. A
  real camera's base URL simply replaces `CAMERA_BASE_URL` in prod.
- `warehouses.id` is lazily created from the first auth attempt that names
  it — there's no "warehouse created" sync with Inventory.

## Endpoints

Unauthenticated (hardware simulator, open within the docker network):

- `POST /auth/fingerprint` — body `{warehouse_id, fingerprint_template}`.
- `POST /auth/nfc` — body `{warehouse_id, card_uid}`.

Both return `{allowed, user_id?, denial_reason?}`.

Admin-only (Gateway-routed, `X-Internal-Token` role `admin`):

- `GET /users` — filterable by `auth_type`, `is_active`.
- `POST /users` — register an employee (fingerprint) or supplier (NFC).
- `PATCH /users/{id}` — update `name`, `is_active`, `warehouse_ids`.
- `DELETE /users/{id}` — remove a user (revokes access).
- `GET /visit-log` — filterable by `warehouse_id`, `user_id`, `auth_type`,
  `success`, `date_from`/`date_to`; includes `video_url`.
- `GET /warehouses` — list warehouses (lazily created from auth attempts).
- `PATCH /warehouses/{id}` — rename a warehouse.

## Local dev without Docker

```bash
cd services/security
cp .env.example .env   # point DATABASE_URL at a local Postgres
uv sync
uv run alembic upgrade head
uv run uvicorn security.main:create_app --factory --reload
```

Run tests (self-contained, in-memory SQLite, no DB needed):

```bash
uv run pytest
```

## Via docker compose

```bash
docker compose up -d --build security-db security mock-camera
```

Reachable through nginx at `/api/security/*` (see
[nginx/nginx.conf](../../nginx/nginx.conf)) for the admin-facing endpoints.
`POST /auth/fingerprint` / `POST /auth/nfc` are meant to be called directly
over the compose network (`http://security:8000`), bypassing the Gateway —
same as `telemetry-simulator`'s direct call to `POST /measurements`.

End-to-end saga verification against the real gateway and real
Firebase-issued tokens:

```bash
docker compose up -d --build
./scripts/test-security-saga.sh
```

Manual check: `GET /visit-log` returns entries with `video_url` set;
opening that URL in a browser plays mock-camera's fixed test clip.

## Migrations

New migration after changing `src/security/models.py`:

```bash
DATABASE_URL=postgresql+asyncpg://security:security@localhost:5437/security \
  uv run alembic revision --autogenerate -m "describe the change"
```
