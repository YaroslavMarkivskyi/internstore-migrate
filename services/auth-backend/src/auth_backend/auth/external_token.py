from typing import Literal

import jwt
from pydantic import BaseModel


class ExternalClaims(BaseModel):
    sub: str
    email: str | None = None
    role: Literal["customer", "admin"]


# PyJWKClient caches signing keys in-process and only refetches on an
# unrecognized `kid`, so verification never blocks on a call to Keycloak.
class ExternalTokenVerifier:
    def __init__(self, issuer: str, jwks_uri: str) -> None:
        self._issuer = issuer
        self._jwk_client = jwt.PyJWKClient(jwks_uri)

    def verify(self, token: str) -> ExternalClaims:
        signing_key = self._jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(token, signing_key.key, algorithms=["RS256"], issuer=self._issuer)

        sub = payload.get("sub")
        if not sub:
            raise ValueError("Token missing sub claim")

        roles = (payload.get("realm_access") or {}).get("roles", [])
        role: Literal["customer", "admin"] | None
        if "admin" in roles:
            role = "admin"
        elif "customer" in roles:
            role = "customer"
        else:
            role = None
        if role is None:
            raise ValueError("Token missing customer/admin role")

        return ExternalClaims(sub=sub, email=payload.get("email"), role=role)
