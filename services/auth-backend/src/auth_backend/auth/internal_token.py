import time
from typing import Literal

import jwt
from pydantic import BaseModel

ISSUER = "internstore-gateway"


# Narrower than ExternalClaims: only what minting actually needs. Guests
# never present a Keycloak token, so there's no ExternalClaims for them —
# this shape lets the guest branch in main.py mint a token without
# fabricating a fake external-claims object.
class MintableClaims(BaseModel):
    sub: str
    role: Literal["customer", "admin", "guest"]


def mint_internal_token(claims: MintableClaims, secret: str, ttl_seconds: int) -> str:
    now = int(time.time())
    payload = {
        "sub": claims.sub,
        "role": claims.role,
        "iss": ISSUER,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# STR-146: the internal-token refresh path. An internal token is only ever
# 60s (INTERNAL_TOKEN_TTL_SECONDS) — fine for a single request, but the
# shopping agent's ReAct loop (services/ai-assistant) can span several
# sequential LLM + tool-call round trips and outlive that. Rather than
# minting a *new* identity, this re-mints the exact same sub/role with a
# fresh exp, so the caller must already hold a validly-signed, not-yet-expired
# token — refresh extends a live session, it never resurrects an expired one
# or lets a caller claim a different identity.
def verify_internal_token_for_refresh(token: str, secret: str) -> MintableClaims:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], issuer=ISSUER)
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid internal token") from exc

    sub = payload.get("sub")
    role = payload.get("role")
    if not sub or role not in ("customer", "admin", "guest"):
        raise ValueError("Invalid internal token claims")
    return MintableClaims(sub=sub, role=role)
