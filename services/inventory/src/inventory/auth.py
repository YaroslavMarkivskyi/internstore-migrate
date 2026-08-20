import jwt

ISSUER = "internstore-gateway"


# The identity this service presents on its own outbound calls to Catalog
# (unpublishing a product that just hit zero stock everywhere -- see
# stock_sync.py). Used because those call sites (including the order-events
# Kafka consumer, which is triggered by an event, not an inbound HTTP
# request) have no inbound request token to forward, so this mints a fresh
# one from the same shared secret every service validates against.
#
# This is the only auth-related code inventory's own container carries
# anymore -- verifying *inbound* internal tokens and enforcing
# admin/identity-only access is now inventory-gate's job (nginx
# `auth_request`) + inventory-verify (services/internal-gate) + OPA
# (policies/inventory.rego). See inventory/README.md's Auth section.
def mint_internal_token(secret: str) -> str:
    return jwt.encode({"sub": "inventory", "role": "admin", "iss": ISSUER}, secret, algorithm="HS256")
