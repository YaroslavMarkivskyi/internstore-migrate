import jwt

ISSUER = "internstore-gateway"

# The identity this service presents on every outbound call to Chat/Orders.
SUB = "ai-assistant"
ROLE = "assistant"


# Unlike every other domain service, this one has no inbound REST API for
# other services to authenticate against (no Gateway route — see
# docker-compose.yml) — it only ever makes outbound calls. There's no
# incoming request token to forward (contrast with
# services/orders/src/orders/inventory_client.py), since this service is
# triggered by a Kafka event, not an HTTP request — so it mints its own
# token from the same shared secret every other service validates against.
def mint_internal_token(secret: str) -> str:
    return jwt.encode({"sub": SUB, "role": ROLE, "iss": ISSUER}, secret, algorithm="HS256")
