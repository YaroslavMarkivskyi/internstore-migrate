from typing import Annotated, Literal

import jwt
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel

ISSUER = "internstore-gateway"


class InternalClaims(BaseModel):
    sub: str
    role: Literal["customer", "admin", "guest", "assistant"]


# Mirrors auth-backend's createInternalTokenVerifier
# (services/auth-backend/src/auth/internalToken.ts) and catalog's/inventory's
# copies of the same. Every domain service validates the Gateway-minted
# internal token locally against the shared HMAC secret — no call back to
# auth-backend or Firebase. Never trust X-User-Id/X-User-Role headers
# directly; only the claims that come out of this verification.
def verify_internal_token(token: str, secret: str) -> InternalClaims:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], issuer=ISSUER)
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid internal token") from exc

    sub = payload.get("sub")
    role = payload.get("role")
    if not sub or role not in ("customer", "admin", "guest", "assistant"):
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


# GET /orders/admin also accepts the AI Assistant's "assistant" role, scoped
# by the owner_id query param below — it's a read-only internal caller
# building customer-order context for a chat reply, same trust level as
# admin (both bypass the "own orders only" restriction on GET /orders).
def require_admin_or_assistant(
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
) -> InternalClaims:
    if claims.role not in ("admin", "assistant"):
        raise HTTPException(status_code=403, detail="Admin or assistant role required")
    return claims


# The identity checkout-workflow's Temporal activities present when calling
# Orders' /internal/checkout-workflow/* endpoints (create_order,
# update_order_status, mark_order_rejected) — same pattern as inventory's
# mint_internal_token, used because there's no inbound request token to
# forward from inside a Temporal activity.
def mint_internal_token(secret: str) -> str:
    return jwt.encode({"sub": "checkout-workflow", "role": "admin", "iss": ISSUER}, secret, algorithm="HS256")
