"""Identity for the OAuth `/authorize` step — federated to the project's
Firebase (the same IdP every other InternStore login uses).

The `/oauth/login` page collects an email + password and exchanges them with
Firebase's Identity Toolkit REST API (the emulator locally) for an ID token.
We then read `sub` / `email` / `role` out of that token's payload.

Demo scope: the ID token payload is decoded, not cryptographically verified
— the password exchange itself is the authentication, and the emulator signs
with `alg: none`. A real deployment verifies via the Firebase Admin SDK /
Google's JWKS.
"""

import base64
import json

import httpx
from pydantic import BaseModel


class FirebaseIdentity(BaseModel):
    sub: str
    email: str | None = None
    role: str = "customer"


class FirebaseAuthError(Exception):
    pass


def _decode_payload(id_token: str) -> dict:
    try:
        _, payload, *_ = id_token.split(".")
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception as exc:  # noqa: BLE001
        raise FirebaseAuthError("Malformed Firebase ID token") from exc


class FirebaseAuthClient:
    def __init__(self, identity_toolkit_url: str, web_api_key: str, timeout_seconds: float = 10.0) -> None:
        self._url = identity_toolkit_url.rstrip("/")
        self._key = web_api_key
        self._timeout = timeout_seconds

    async def sign_in(self, email: str, password: str) -> FirebaseIdentity:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._url}/v1/accounts:signInWithPassword",
                params={"key": self._key},
                json={"email": email, "password": password, "returnSecureToken": True},
            )
        if resp.status_code != 200:
            raise FirebaseAuthError("Invalid email or password")
        id_token = resp.json().get("idToken")
        if not id_token:
            raise FirebaseAuthError("Firebase returned no ID token")

        payload = _decode_payload(id_token)
        sub = payload.get("user_id") or payload.get("sub")
        if not sub:
            raise FirebaseAuthError("Firebase ID token has no subject")
        role = payload.get("role")
        return FirebaseIdentity(
            sub=sub,
            email=payload.get("email"),
            role=role if role in ("customer", "admin") else "customer",
        )
