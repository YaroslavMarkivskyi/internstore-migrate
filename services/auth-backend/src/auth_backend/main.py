from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from auth_backend.auth.external_token import ExternalTokenVerifier
from auth_backend.auth.guest_session import GUEST_SESSION_TTL_SECONDS, GuestSessionStore
from auth_backend.auth.internal_token import MintableClaims, mint_internal_token
from auth_backend.auth.revocation import RevocationChecker
from auth_backend.config import Settings, load_settings

# Catalog browsing, cart/checkout, chat, and chat attachment uploads are
# reachable without a Keycloak login — these are the only paths
# /auth/verify grants a role=guest fallback token for. Order history
# (/api/orders/orders) is deliberately NOT included: a guest can check out
# but must register/log in to see past orders. /api/catalog is safe to
# blanket-allow despite covering catalog's admin-only write endpoints too
# (POST /categories, POST/PATCH /products) — Catalog's own require_admin
# dependency rejects a guest token there; this allowlist only controls
# whether auth-backend issues a guest fallback token at all, not what that
# token is allowed to do downstream. Same reasoning for /ws/room and
# /api/chat/rooms, shared by guest-usable paths (WS connect, attachment
# upload) and admin-only ones (GET /rooms, DELETE /rooms/:id).
GUEST_ALLOWED_PATH_PREFIXES = [
    "/api/catalog",
    "/api/orders/cart",
    "/api/orders/checkout",
    "/ws/room",
    "/api/chat/rooms",
]
GUEST_COOKIE_NAME = "is_guest_id"


def is_guest_allowed_path(original_uri: str) -> bool:
    path = original_uri.split("?")[0]
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in GUEST_ALLOWED_PATH_PREFIXES)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.redis = redis
    app.state.guest_session_store = GuestSessionStore(redis)
    app.state.revocation_checker = RevocationChecker(settings)
    app.state.external_token_verifier = ExternalTokenVerifier(settings.keycloak_issuer, settings.keycloak_jwks_uri)

    try:
        yield
    finally:
        await redis.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="auth-backend", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Demonstrates AUTH-03: validate the Keycloak-issued external token via
    # JWKS (no per-request call to Keycloak), then mint a short-lived internal
    # token that downstream services trust without contacting Keycloak or the
    # Gateway.
    @app.get("/me")
    async def me(request: Request) -> Response:
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse({"error": "Missing bearer token"}, status_code=401)

        external_token = auth_header.removeprefix("Bearer ")
        verifier: ExternalTokenVerifier = request.app.state.external_token_verifier

        try:
            claims = verifier.verify(external_token)
            internal_token = mint_internal_token(
                MintableClaims(sub=claims.sub, role=claims.role),
                settings.internal_token_secret,
                settings.internal_token_ttl_seconds,
            )
        except Exception:
            return JSONResponse({"error": "Invalid token"}, status_code=401)

        return JSONResponse(
            {"sub": claims.sub, "email": claims.email, "role": claims.role, "internalToken": internal_token}
        )

    # nginx `auth_request` target: on-prem entry point. Same validation logic
    # an AWS ALB Lambda@Edge/authorizer would call — this handler has no
    # nginx-specific code, only HTTP status + headers, so it's reusable as-is
    # under either topology (see services/auth-backend/README.md).
    @app.get("/auth/verify")
    async def verify(request: Request) -> Response:
        auth_header = request.headers.get("authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            # No external token presented. Only fall back to a guest identity
            # on the paths Orders explicitly allows guests on (X-Original-URI
            # is set by nginx's auth_request subrequest — see nginx.conf) —
            # every other route still 401s exactly as before.
            original_uri = request.headers.get("x-original-uri")
            if not original_uri or not is_guest_allowed_path(original_uri):
                return Response(status_code=401)

            guest_session_store: GuestSessionStore = request.app.state.guest_session_store
            try:
                existing_guest_id = request.cookies.get(GUEST_COOKIE_NAME)
                guest_id: str
                if existing_guest_id and await guest_session_store.lookup(existing_guest_id):
                    guest_id = existing_guest_id
                    set_cookie = False
                else:
                    guest_id = await guest_session_store.create()
                    set_cookie = True

                internal_token = mint_internal_token(
                    MintableClaims(sub=guest_id, role="guest"),
                    settings.internal_token_secret,
                    settings.internal_token_ttl_seconds,
                )
            except Exception:
                return Response(status_code=401)

            response = Response(status_code=200)
            if set_cookie:
                response.set_cookie(
                    GUEST_COOKIE_NAME,
                    guest_id,
                    max_age=GUEST_SESSION_TTL_SECONDS,
                    path="/",
                    httponly=True,
                    secure=True,
                    # Must be "none", not "lax" -- the frontend (Vite dev
                    # server, http://localhost:5180) and this gateway
                    # (https://localhost:8443) differ in *scheme*, which
                    # modern browsers' schemeful-same-site logic treats as
                    # cross-site regardless of matching host. A Lax cookie
                    # is never attached to cross-site fetch/XHR (only
                    # top-level navigations), so it silently never comes
                    # back on the frontend's actual cart/checkout calls --
                    # every request mints a fresh guest session and the
                    # cart looks empty despite "add to cart" reporting
                    # success. None still requires Secure (already set).
                    samesite="none",
                )
            response.headers["X-User-Id"] = guest_id
            response.headers["X-User-Role"] = "guest"
            response.headers["X-Internal-Token"] = internal_token
            return response

        external_token = auth_header.removeprefix("Bearer ")
        verifier: ExternalTokenVerifier = request.app.state.external_token_verifier
        revocation_checker: RevocationChecker = request.app.state.revocation_checker

        try:
            claims = verifier.verify(external_token)
            if await revocation_checker.is_revoked(external_token):
                return Response(status_code=401)
            internal_token = mint_internal_token(
                MintableClaims(sub=claims.sub, role=claims.role),
                settings.internal_token_secret,
                settings.internal_token_ttl_seconds,
            )
        except Exception:
            return Response(status_code=401)

        response = Response(status_code=200)
        response.headers["X-User-Id"] = claims.sub
        response.headers["X-User-Role"] = claims.role
        response.headers["X-Internal-Token"] = internal_token
        return response

    return app
