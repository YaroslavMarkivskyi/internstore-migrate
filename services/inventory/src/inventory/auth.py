from collections.abc import Callable, Coroutine
from typing import Annotated, Any, Literal

import jwt
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel

from inventory.authz import AuthzClient, get_authz_client

ISSUER = "internstore-gateway"


class InternalClaims(BaseModel):
    sub: str
    role: Literal["customer", "admin", "guest"]


# Mirrors auth-backend's createInternalTokenVerifier
# (services/auth-backend/src/auth/internalToken.ts) and catalog's copy of the
# same. Every domain service validates the Gateway-minted internal token
# locally against the shared HMAC secret — no call back to auth-backend or
# Firebase. Never trust X-User-Id/X-User-Role headers directly; only the
# claims that come out of this verification.
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


# STR-140: dependency factory replacing require_admin at stock-mutation
# call sites -- same shape/call-site (`dependencies=[Depends(...)]`), but
# the decision now comes from the OPA sidecar (see policies/inventory.rego)
# instead of an inline role check.
def require_authz(action: str, resource_type: str) -> Callable[..., Coroutine[Any, Any, InternalClaims]]:
    async def _check(
        claims: Annotated[InternalClaims, Depends(get_internal_claims)],
        authz: Annotated[AuthzClient, Depends(get_authz_client)],
    ) -> InternalClaims:
        if not await authz.check(
            subject={"role": claims.role, "sub": claims.sub},
            action=action,
            resource={"type": resource_type},
        ):
            raise HTTPException(status_code=403, detail="Not authorized")
        return claims

    return _check


# The identity this service presents on its own outbound calls to Catalog
# (unpublishing a product that just hit zero stock everywhere -- see
# stock_sync.py). Same pattern as ai-assistant's mint_internal_token: some
# of the call sites (the order-events Kafka consumer) have no inbound
# request token to forward, since they're triggered by an event, not an
# HTTP request, so this mints a fresh one from the same shared secret every
# service validates against. Used uniformly (even from the HTTP-triggered
# call sites) so both paths behave identically instead of one forwarding a
# borrowed token and the other minting.
def mint_internal_token(secret: str) -> str:
    return jwt.encode({"sub": "inventory", "role": "admin", "iss": ISSUER}, secret, algorithm="HS256")
