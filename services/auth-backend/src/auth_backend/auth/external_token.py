from typing import Literal

from firebase_admin import auth as firebase_auth
from pydantic import BaseModel


class ExternalClaims(BaseModel):
    sub: str
    email: str | None = None
    role: Literal["customer", "admin"]


# STR-155: verifies a Firebase ID token via the Firebase Admin SDK.
# Signing-cert fetch/caching and revocation lookup are both handled inside
# firebase_admin itself against the process-wide default App (initialized
# once in main.py's lifespan) — there's no local key-fetch client to hold
# onto here.
class ExternalTokenVerifier:
    def verify(self, token: str) -> ExternalClaims:
        # check_revoked=True does an extra per-request lookup (get_user)
        # comparing the token's `iat` against the user's
        # tokens_valid_after_timestamp. Per Firebase Admin SDK's own source,
        # that lookup fails closed already — a network error talking to
        # Firebase propagates as an exception rather than being swallowed,
        # so an unreachable Firebase rejects the token here.
        decoded = firebase_auth.verify_id_token(token, check_revoked=True)

        sub = decoded.get("uid")
        if not sub:
            raise ValueError("Token missing uid claim")

        # Custom claims are set out-of-band via
        # firebase_admin.auth.set_custom_user_claims (an admin-side script,
        # not part of this request path).
        role = decoded.get("role")
        if role not in ("customer", "admin"):
            raise ValueError("Token missing customer/admin role")

        return ExternalClaims(sub=sub, email=decoded.get("email"), role=role)
