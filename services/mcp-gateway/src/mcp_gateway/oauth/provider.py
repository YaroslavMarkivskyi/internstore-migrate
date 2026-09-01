"""A minimal OAuth 2.1 Authorization Server co-located in the Gateway.

The `mcp` SDK supplies the `/authorize`, `/token`, `/register` and metadata
handlers (see `create_auth_routes`); this provider is the state + policy
behind them. Identity is federated to Firebase at the `/authorize` step (see
`login.py` / `firebase.py`).

Stores (clients / codes / refresh tokens) are in-memory — fine for the demo,
where a restart just means MCP clients re-register and re-auth. Issued
access tokens are RS256 JWTs (`keys.SigningKey`) scoped to `mcp:shopping`
with `aud` = the MCP resource URL, so the resource-server side is a plain
signature + `iss`/`aud`/`exp` check.
"""

import secrets
import time

import jwt
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from mcp_gateway.oauth.firebase import FirebaseIdentity
from mcp_gateway.oauth.keys import SigningKey

SCOPE = "mcp:shopping"
_ACCESS_TTL = 3600
_CODE_TTL = 300
_REFRESH_TTL = 30 * 24 * 3600


class _PendingAuth:
    __slots__ = ("client_id", "params")

    def __init__(self, client_id: str, params: AuthorizationParams) -> None:
        self.client_id = client_id
        self.params = params


class GatewayOAuthProvider(OAuthAuthorizationServerProvider):
    def __init__(self, *, issuer_url: str, resource_url: str, signing_key: SigningKey, login_path: str) -> None:
        self._issuer = issuer_url.rstrip("/")
        self._resource = resource_url
        self._key = signing_key
        self._login_path = login_path
        self._clients: dict[str, OAuthClientInformationFull] = {}
        self._pending: dict[str, _PendingAuth] = {}
        self._codes: dict[str, AuthorizationCode] = {}
        self._refresh: dict[str, RefreshToken] = {}

    # ── Dynamic Client Registration ──────────────────────────────────────
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._clients[client_info.client_id] = client_info

    # ── Authorization (federated to Firebase via the login page) ──────────
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        rid = secrets.token_urlsafe(24)
        self._pending[rid] = _PendingAuth(client.client_id, params)
        return f"{self._issuer}{self._login_path}?rid={rid}"

    def complete_login(self, rid: str, identity: FirebaseIdentity) -> str:
        """Called by the login handler once Firebase has authenticated the
        user. Mints the auth code and returns the client redirect URL."""
        pending = self._pending.pop(rid, None)
        if pending is None:
            raise KeyError("Unknown or expired login session")
        params = pending.params
        code = f"code_{secrets.token_urlsafe(32)}"
        self._codes[code] = AuthorizationCode(
            code=code,
            scopes=[SCOPE],
            expires_at=time.time() + _CODE_TTL,
            client_id=pending.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
            subject=identity.sub,
        )
        redirect_params: dict[str, str] = {"code": code}
        if params.state:
            redirect_params["state"] = params.state
        return construct_redirect_uri(str(params.redirect_uri), **redirect_params)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self._codes.get(authorization_code)
        if code is None or code.client_id != client.client_id or code.expires_at < time.time():
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self._codes.pop(authorization_code.code, None)
        return self._issue(client.client_id, authorization_code.subject or "unknown")

    # ── Refresh ──────────────────────────────────────────────────────────
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        rt = self._refresh.get(refresh_token)
        if rt is None or rt.client_id != client.client_id:
            return None
        if rt.expires_at is not None and rt.expires_at < time.time():
            return None
        return rt

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        self._refresh.pop(refresh_token.token, None)
        return self._issue(client.client_id, refresh_token.subject or "unknown")

    # ── Resource-server side ─────────────────────────────────────────────
    async def load_access_token(self, token: str) -> AccessToken | None:
        try:
            claims = self._key.decode(token, issuer=self._issuer, audience=self._resource)
        except jwt.InvalidTokenError:
            return None
        return AccessToken(
            token=token,
            client_id=claims.get("client_id", ""),
            scopes=claims.get("scope", "").split(),
            expires_at=claims.get("exp"),
            resource=self._resource,
            subject=claims.get("sub"),
            claims=claims,
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        return await self.load_access_token(token)

    async def revoke_token(self, token) -> None:
        self._refresh.pop(getattr(token, "token", token), None)

    # ── internals ────────────────────────────────────────────────────────
    def _issue(self, client_id: str, subject: str) -> OAuthToken:
        now = int(time.time())
        access = self._key.sign(
            {
                "iss": self._issuer,
                "aud": self._resource,
                "sub": subject,
                "client_id": client_id,
                "scope": SCOPE,
                "iat": now,
                "exp": now + _ACCESS_TTL,
            }
        )
        refresh = f"refresh_{secrets.token_urlsafe(32)}"
        self._refresh[refresh] = RefreshToken(
            token=refresh,
            client_id=client_id,
            scopes=[SCOPE],
            expires_at=now + _REFRESH_TTL,
            subject=subject,
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=_ACCESS_TTL,
            scope=SCOPE,
            refresh_token=refresh,
        )
