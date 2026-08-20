package common

import future.keywords.if

# Verified from input.token (the raw X-Internal-Token header, HS256,
# HMAC-signed by auth-backend — see
# services/auth-backend/src/auth_backend/auth/internal_token.py). This is
# the migrated path: OPA verifies the token itself instead of trusting an
# already-decoded input.subject the caller hands it. See catalog.rego,
# the first service migrated onto this (spike; the rest of
# services/*/auth.py still do their own jwt.decode()).
subject := payload if {
	[valid, _, payload] := io.jwt.decode_verify(input.token, {
		"secret": opa.runtime().env.INTERNAL_TOKEN_SECRET,
		"alg": "HS256",
		"iss": "internstore-gateway",
	})
	valid
}

# Legacy path: services not yet migrated still decode/verify the token
# themselves (services/<name>/auth.py) and pass the already-trusted
# claims as input.subject directly. Only used when the caller sends no
# input.token at all — remove once every service sends input.token
# instead and does its own jwt.decode() nowhere anymore.
subject := input.subject if {
	not input.token
	input.subject
}

# True when the calling subject holds the "admin" role. Every domain
# policy in this directory treats admin as "can do anything" — this rule
# is the single place that fact is encoded, so it only needs auditing once.
is_admin if {
	subject.role == "admin"
}

# True when the resource being acted on is owned by the calling subject
# (e.g. an order's owner_id matching the customer's own sub). Domain
# policies combine this with their own action/resource.type checks —
# this rule only knows about the ownership relationship itself.
is_resource_owner if {
	input.resource.owner == subject.sub
}
