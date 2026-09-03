"""RS256 signing key for the Gateway's OAuth access tokens + its JWKS.

For the demo the key is generated at process start (tokens don't survive a
restart — MCP clients just re-auth). A real deployment would load a stable
key from a secret and rotate it with overlapping `kid`s.
"""

import base64
import hashlib

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _b64u(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class SigningKey:
    def __init__(self, private_pem: bytes | None = None) -> None:
        if private_pem:
            self._key = serialization.load_pem_private_key(private_pem, password=None)
        else:
            self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub_pem = self._key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.kid = hashlib.sha256(pub_pem).hexdigest()[:16]

    def sign(self, claims: dict) -> str:
        return jwt.encode(claims, self._private_pem(), algorithm="RS256", headers={"kid": self.kid})

    def decode(self, token: str, *, issuer: str, audience: str) -> dict:
        return jwt.decode(
            token,
            self._public_pem(),
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
        )

    def jwks(self) -> dict:
        numbers = self._key.public_key().public_numbers()
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self.kid,
                    "n": _b64u(numbers.n),
                    "e": _b64u(numbers.e),
                }
            ]
        }

    def _private_pem(self) -> bytes:
        return self._key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    def _public_pem(self) -> bytes:
        return self._key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
