# internal-gate

Translates OPA's JSON policy decision into the HTTP status/headers nginx's
`auth_request` needs, so a domain service's `auth_request`-gated sidecar
chain can enforce internal-token verification and role checks without the
domain service itself carrying any auth code.

## Why this exists

nginx's `auth_request` + `auth_request_set $x $upstream_http_...` only
reads response headers from a subrequest answered by a real proxied
upstream (`proxy_pass`/fastcgi/etc) — verified directly that neither a
bare `return`+`add_header` nor an njs `js_content` response propagates
through `$upstream_http_*`, even though the subrequest's own response
headers are set correctly either way. OPA's own REST API always returns
`200` regardless of whether a policy evaluated to `true` or `false` (it
never maps a decision onto the HTTP status code itself), so nginx can't
point `auth_request` at OPA directly either. This is the real HTTP service
that bridges the two, mirroring the exact pattern
[nginx/nginx.conf](../../nginx/nginx.conf)'s `/internal/auth-verify`
already uses against auth-backend at the external Gateway boundary — just
for the *internal* token, one instance per gated domain service.

## Endpoints

- `GET /health` — liveness check.
- `GET /verify` — the `auth_request` target. Reads `X-Internal-Token`
  (required), `X-Original-Method`, and optionally `X-Required-Role`, POSTs
  `{"input": {"token": ..., "method": ..., "required_role"?: ...}}` to
  `${OPA_URL}/v1/data/${OPA_PACKAGE}`, and returns:
  - `401` if the token is missing or OPA's `subject` rule is undefined
    (missing/forged/expired/wrong-issuer token, or OPA itself is
    unreachable — fails closed)
  - `403` if the token verified but the package's `allow` rule is `false`
  - `200` with `X-User-Id`/`X-User-Role` response headers otherwise

No domain-specific logic lives here — `OPA_PACKAGE` is the only thing
that varies per deployment (see docker-compose.yml's `catalog-verify`).
`X-Required-Role` is a generic passthrough for services whose
access-control shape needs more than a flat admin-only gate: inventory
sets it from its own nginx map to distinguish its identity-only routes
(any authenticated caller — `check-availability`/`reserve`/`release`) from
its admin-only ones, and `policies/inventory.rego` reads
`input.required_role` accordingly. Omitted entirely for services that
don't need the distinction (catalog/security/payments), so it's simply
absent from `input` there.

## Config

`OPA_URL` (default `http://localhost:8181`, sidecar-local — see the OPA
container it's deployed alongside), `OPA_PACKAGE` (required), `PORT`
(default `8090`).

## Local dev without Docker

```bash
cd services/internal-gate
uv sync
OPA_PACKAGE=catalog uv run uvicorn internal_gate.main:create_app --factory --reload
```

## Tests

```bash
uv run pytest
```
