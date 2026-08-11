from typing import Annotated, Literal

import jwt
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel

ISSUER = "internstore-gateway"


class InternalClaims(BaseModel):
    sub: str
    role: Literal["customer", "admin"]


# Same internal-token verification pattern as every other domain service
# (see telemetry/src/telemetry/auth.py, the direct template for this
# file). Never trust X-User-Id/X-User-Role headers directly — only claims
# that come out of this local HMAC verification.
def verify_internal_token(token: str, secret: str) -> InternalClaims:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], issuer=ISSUER)
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid internal token") from exc

    sub = payload.get("sub")
    role = payload.get("role")
    if not sub or role not in ("customer", "admin"):
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
