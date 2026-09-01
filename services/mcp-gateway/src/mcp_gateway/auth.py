from typing import Annotated, Literal

import jwt
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel

ISSUER = "internstore-gateway"


class InternalClaims(BaseModel):
    sub: str
    role: Literal["customer", "admin", "guest", "assistant"]


# Mirrors every other domain service's copy of the same verifier (see
# services/orders/src/orders/auth.py). The Gateway itself is an internal
# service with no browser-facing route (no nginx location — see
# docker-compose.yml) -- callers are other services (AI Assistant) or a
# future MCP-compatible agent runtime, always presenting a Gateway-minted
# internal token, never a raw Firebase token.
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


# STR-146: the Gateway used to mint its own admin-identity token
# (sub="mcp-gateway", role="admin") for every outbound call to a domain
# service, regardless of who actually called /mcp/tools/call — fine for a
# read-only tool set, but wrong once add_to_cart/remove_from_cart exist:
# ownership has to resolve against the real customer, not the Gateway. The
# Gateway now forwards the caller's own already-verified token unchanged
# (see main.py's call_tool_endpoint and router.call_tool) instead of minting
# a new identity — there is no more Gateway-owned outbound token to mint.
def get_raw_internal_token(x_internal_token: Annotated[str | None, Header()] = None) -> str:
    if x_internal_token is None:
        raise HTTPException(status_code=401, detail="Missing internal token")
    return x_internal_token
