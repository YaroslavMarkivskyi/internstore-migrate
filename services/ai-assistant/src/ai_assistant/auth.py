from typing import Annotated, Literal

import jwt
from fastapi import Header, HTTPException
from pydantic import BaseModel

ISSUER = "internstore-gateway"

# The identity this service presents on every outbound call to Chat/Orders
# that it makes *as itself* (posting the assistant's own reply, reading chat
# history) — unrelated to the customer-forwarded token the shopping ReAct
# loop uses below, which is never minted by this service.
SUB = "ai-assistant"
ROLE = "assistant"


# Historically this service had no inbound REST API at all — it was purely
# Kafka-triggered, so there was no incoming request token to forward (see
# chat_events.py, and mint_internal_token below for the self-minted identity
# that predates this). STR-146 adds one real inbound route, POST
# /agent/shopping, called synchronously by Chat with the customer's own
# internal-token forwarded in the header — this mirrors every other domain
# service's copy of the same verifier (e.g. services/orders/src/orders/auth.py)
# for that route specifically.
def mint_internal_token(secret: str) -> str:
    return jwt.encode({"sub": SUB, "role": ROLE, "iss": ISSUER}, secret, algorithm="HS256")


class InternalClaims(BaseModel):
    sub: str
    role: Literal["customer", "admin", "guest", "assistant"]


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


def get_raw_internal_token(x_internal_token: Annotated[str | None, Header()] = None) -> str:
    if x_internal_token is None:
        raise HTTPException(status_code=401, detail="Missing internal token")
    return x_internal_token
