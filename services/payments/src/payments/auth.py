from typing import Annotated, Literal

import jwt
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel

ISSUER = "internstore-gateway"


class InternalClaims(BaseModel):
    sub: str
    role: Literal["customer", "admin", "guest", "assistant"]


# Mirrors inventory's/catalog's copy of the same verifier (repo convention
# is per-service duplication, not a shared lib — see auth-backend's
# createInternalTokenVerifier). Payments is never called by nginx/the
# browser though — only by the checkout-workflow Temporal worker, which
# mints its own token via mint_internal_token below (no inbound request to
# forward from inside an activity).
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


# The identity checkout-workflow's Temporal activities present when calling
# Payments — same pattern as inventory's mint_internal_token (used from
# Kafka-consumer call sites that have no inbound request token to forward).
def mint_internal_token(secret: str) -> str:
    return jwt.encode({"sub": "checkout-workflow", "role": "admin", "iss": ISSUER}, secret, algorithm="HS256")
