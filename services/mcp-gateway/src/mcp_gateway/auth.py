from typing import Annotated, Literal

import jwt
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel

ISSUER = "internstore-gateway"

# The identity this service presents on every outbound call to a domain
# service. "admin" is the highest internal trust level any domain service
# recognizes (see e.g. services/orders/src/orders/auth.py's
# require_admin_or_assistant) -- the Gateway fans a single MCP tool call out
# to whichever domain service holds the data, so it needs the same read
# access an admin has everywhere, not a narrower per-domain role.
SUB = "mcp-gateway"
ROLE = "admin"


class InternalClaims(BaseModel):
    sub: str
    role: Literal["customer", "admin", "guest", "assistant"]


# Mirrors every other domain service's copy of the same verifier (see
# services/orders/src/orders/auth.py). The Gateway itself is an internal
# service with no browser-facing route (no nginx location — see
# docker-compose.yml) -- callers are other services (AI Assistant) or a
# future MCP-compatible agent runtime, always presenting a Gateway-minted
# internal token, never a raw Keycloak token.
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


def mint_internal_token(secret: str) -> str:
    return jwt.encode({"sub": SUB, "role": ROLE, "iss": ISSUER}, secret, algorithm="HS256")
