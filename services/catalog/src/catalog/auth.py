from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel

from catalog.authz import AuthzClient, AuthzResult, get_authz_client


class InternalClaims(BaseModel):
    sub: str
    role: str


# Spike: catalog no longer decodes/verifies the internal token itself --
# OPA's common.rego does that (io.jwt.decode_verify), reused across every
# call site here instead of one jwt.decode() copy per domain service. See
# policies/common.rego and AuthzClient.identify/check.
def get_internal_token(x_internal_token: Annotated[str | None, Header()] = None) -> str:
    if x_internal_token is None:
        raise HTTPException(status_code=401, detail="Missing internal token")
    return x_internal_token


async def get_internal_claims(
    token: Annotated[str, Depends(get_internal_token)],
    authz: Annotated[AuthzClient, Depends(get_authz_client)],
) -> InternalClaims:
    subject = await authz.identify(token)
    if subject is None:
        raise HTTPException(status_code=401, detail="Invalid internal token")
    return InternalClaims(sub=subject["sub"], role=subject["role"])


async def require_admin(
    claims: Annotated[InternalClaims, Depends(get_internal_claims)],
) -> InternalClaims:
    if claims.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return claims


# Shared by every OPA-routed call site (categories/products POST/PATCH):
# an AuthzResult with no subject means the token itself never verified
# (missing/forged/expired/wrong-issuer) -- 401, not authenticated. A
# verified subject that OPA still denied -- 403, not authorized.
def enforce(result: AuthzResult, forbidden_detail: str) -> None:
    if result.subject is None:
        raise HTTPException(status_code=401, detail="Invalid internal token")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=forbidden_detail)
