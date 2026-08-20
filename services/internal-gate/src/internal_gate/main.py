from typing import Annotated

import httpx
from fastapi import FastAPI, Header, HTTPException, Response

from internal_gate.config import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="internal-gate")
    app.state.settings = settings

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # nginx's `auth_request /internal/verify;` proxy_passes here (see
    # nginx/internal-gate.conf). auth_request only looks at the response
    # status code (2xx forwards the real request, anything else is
    # returned to the client verbatim) and, via auth_request_set, a
    # couple of response headers -- both of which only work when this
    # location is reached through a real proxied upstream, not a
    # return/add_header/js_content response (verified directly: neither
    # propagates through $upstream_http_* the way auth_request needs).
    # That's the whole reason this is a separate service instead of nginx
    # config alone.
    #
    # This is deliberately generic -- no catalog-specific (or any
    # domain-specific) logic lives here. Every domain service gets its
    # own internal-gate instance, parameterized by OPA_PACKAGE, instead
    # of one jwt.decode() copy per service (the thing this replaces --
    # see services/catalog/src/catalog/auth.py's git history).
    @app.get("/verify")
    async def verify(
        response: Response,
        x_internal_token: Annotated[str | None, Header()] = None,
        x_original_method: Annotated[str, Header()] = "GET",
    ) -> dict[str, str]:
        if x_internal_token is None:
            raise HTTPException(status_code=401, detail="Missing internal token")

        settings: Settings = app.state.settings
        try:
            async with httpx.AsyncClient(timeout=settings.opa_timeout_seconds) as client:
                resp = await client.post(
                    f"{settings.opa_url}/v1/data/{settings.opa_package}",
                    json={"input": {"token": x_internal_token, "method": x_original_method}},
                )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # Fail closed: an unreachable/erroring OPA must not silently
            # let the request through, same as the jwt.decode() path this
            # replaces would have on any verification failure.
            raise HTTPException(status_code=401, detail="Authorization check unavailable") from exc

        result = resp.json().get("result") or {}
        subject = result.get("subject")
        if not isinstance(subject, dict) or "sub" not in subject or "role" not in subject:
            # OPA's `subject` rule (policies/common.rego) is undefined for
            # a missing/forged/expired/wrong-issuer token -- no identity
            # at all, so this is "not authenticated", not "not allowed".
            raise HTTPException(status_code=401, detail="Invalid internal token")
        if not result.get("allow", False):
            raise HTTPException(status_code=403, detail="Not authorized")

        # auth_request_set in nginx reads these off the subrequest
        # response and forwards them to the real backend as
        # X-User-Id/X-User-Role -- see nginx/internal-gate.conf.
        response.headers["X-User-Id"] = subject["sub"]
        response.headers["X-User-Role"] = subject["role"]
        return {"sub": subject["sub"], "role": subject["role"]}

    return app
