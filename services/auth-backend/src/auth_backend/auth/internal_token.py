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
