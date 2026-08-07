import jwt

ISSUER = "internstore-gateway"


# The identity checkout-workflow's activities present to Inventory/Orders/
# Payments — same mint_internal_token pattern each of those services'
# own auth.py already has (see e.g. services/inventory/src/inventory/auth.py),
# used because an activity has no inbound request token to forward, only
# the shared HMAC secret every service validates against locally.
def mint_internal_token(secret: str) -> str:
    return jwt.encode({"sub": "checkout-workflow", "role": "admin", "iss": ISSUER}, secret, algorithm="HS256")
