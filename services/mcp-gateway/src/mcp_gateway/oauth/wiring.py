"""Assembles the public-door OAuth surface: the Authorization Server routes
(`/authorize`, `/token`, `/register`, metadata), the JWKS + login routes,
and a dual-door wrapper for the `/mcp` endpoint itself.

`/mcp` serves two callers off one route: an `X-Internal-Token` request (the
in-mesh ADK agents) goes straight to the MCP handler; anything else must
pass the OAuth Bearer chain (`RequireAuthMiddleware`, which also emits the
`WWW-Authenticate` challenge pointing at the protected-resource metadata).
"""

from dataclasses import dataclass

from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
from mcp.server.auth.middleware.bearer_auth import (
    BearerAuthBackend,
    RequireAuthMiddleware,
)
from mcp.server.auth.routes import (
    build_resource_metadata_url,
    create_auth_routes,
    create_protected_resource_routes,
)
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from pydantic import AnyHttpUrl
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from mcp_gateway.config import Settings
from mcp_gateway.oauth.firebase import FirebaseAuthClient
from mcp_gateway.oauth.keys import SigningKey
from mcp_gateway.oauth.login import LOGIN_PATH, build_login_routes
from mcp_gateway.oauth.provider import SCOPE, GatewayOAuthProvider


class _DualDoorASGI:
    def __init__(self, bare_mcp, oauth_guarded) -> None:
        self._bare = bare_mcp
        self._oauth = oauth_guarded

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = dict(scope.get("headers") or [])
        if scope["type"] == "http" and b"x-internal-token" in headers:
            await self._bare(scope, receive, send)
        else:
            await self._oauth(scope, receive, send)


@dataclass
class PublicOAuth:
    endpoint: _DualDoorASGI
    routes: list[Route]
    provider: GatewayOAuthProvider
    firebase: FirebaseAuthClient
    signing_key: SigningKey


def build_public_oauth(settings: Settings, bare_mcp) -> PublicOAuth:
    """Returns the `/mcp` endpoint (dual-door), the extra Starlette routes the
    public door needs, and the provider/firebase/key for tests."""
    issuer = AnyHttpUrl(settings.public_base_url)
    resource = AnyHttpUrl(settings.public_mcp_url)
    key = SigningKey(settings.oauth_signing_key_pem.encode() if settings.oauth_signing_key_pem else None)
    provider = GatewayOAuthProvider(
        issuer_url=settings.public_base_url,
        resource_url=settings.public_mcp_url,
        signing_key=key,
        login_path=LOGIN_PATH,
    )
    firebase = FirebaseAuthClient(settings.firebase_identity_toolkit_url, settings.firebase_web_api_key)

    guarded = AuthContextMiddleware(
        AuthenticationMiddleware(
            RequireAuthMiddleware(bare_mcp, [SCOPE], build_resource_metadata_url(resource)),
            backend=BearerAuthBackend(provider),
        )
    )

    async def jwks(_request: Request) -> JSONResponse:
        return JSONResponse(key.jwks())

    routes: list[Route] = [
        *create_auth_routes(
            provider=provider,
            issuer_url=issuer,
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]
            ),
            revocation_options=RevocationOptions(enabled=True),
        ),
        *create_protected_resource_routes(
            resource_url=resource,
            authorization_servers=[issuer],
            scopes_supported=[SCOPE],
        ),
        *build_login_routes(provider, firebase),
        Route("/.well-known/jwks.json", jwks, methods=["GET"]),
    ]
    return PublicOAuth(_DualDoorASGI(bare_mcp, guarded), routes, provider, firebase, key)
