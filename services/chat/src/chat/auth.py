from typing import Annotated, Literal

import jwt
from fastapi import Depends, Header, HTTPException, Request, WebSocket, WebSocketException, status
from pydantic import BaseModel

ISSUER = "internstore-gateway"


class InternalClaims(BaseModel):
    sub: str
    role: Literal["customer", "admin", "guest"]


# Mirrors auth-backend's createInternalTokenVerifier
# (services/auth-backend/src/auth/internalToken.ts) and every other domain
# service's copy of the same. Every domain service validates the
# Gateway-minted internal token locally against the shared HMAC secret — no
# call back to auth-backend or Keycloak. Never trust X-User-Id/X-User-Role
# headers directly; only the claims that come out of this verification.
def verify_internal_token(token: str, secret: str) -> InternalClaims:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], issuer=ISSUER)
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid internal token") from exc

    sub = payload.get("sub")
    role = payload.get("role")
    if not sub or role not in ("customer", "admin", "guest"):
        raise ValueError("Invalid internal token claims")
    return InternalClaims(sub=sub, role=role)


def get_internal_claims(
    request: Request,
    x_internal_token: Annotated[str | None, Header()] = None,
) -> InternalClaims:
    if x_internal_token is None:
        raise HTTPException(status_code=401, detail="Missing internal token")
    secret: str = request.app.state.settings.internal_token_secret
    try:
        return verify_internal_token(x_internal_token, secret)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid internal token") from exc


def require_admin(
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
) -> InternalClaims:
    if claims.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return claims


# WebSocket handshakes go through the same nginx auth_request gate as any
# REST call (see nginx/nginx.conf's /ws/ location) — X-Internal-Token is set
# on the handshake request itself, so this reads it off WebSocket.headers
# instead of FastAPI's Header() DI, which only works for regular routes.
async def get_internal_claims_ws(websocket: WebSocket) -> InternalClaims:
    token = websocket.headers.get("x-internal-token")
    if token is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing internal token")
    secret: str = websocket.app.state.settings.internal_token_secret
    try:
        return verify_internal_token(token, secret)
    except ValueError as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid internal token") from exc
