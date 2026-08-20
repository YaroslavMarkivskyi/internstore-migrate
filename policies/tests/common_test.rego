package common

import future.keywords.if

mock_runtime := {"env": {"INTERNAL_TOKEN_SECRET": "test-secret"}}

sign(payload, secret) := io.jwt.encode_sign(
	{"alg": "HS256", "typ": "JWT"},
	payload,
	{"kty": "oct", "k": base64url.encode(secret)},
)

valid_token := sign({"sub": "admin-1", "role": "admin", "iss": "internstore-gateway"}, "test-secret")

wrong_secret_token := sign({"sub": "attacker", "role": "admin", "iss": "internstore-gateway"}, "not-the-real-secret")

wrong_issuer_token := sign({"sub": "u2", "role": "admin", "iss": "someone-else"}, "test-secret")

test_subject_valid_token if {
	subject == {"sub": "admin-1", "role": "admin", "iss": "internstore-gateway"}
		with input as {"token": valid_token}
		with opa.runtime as mock_runtime
}

test_subject_undefined_for_forged_secret if {
	not subject with input as {"token": wrong_secret_token} with opa.runtime as mock_runtime
}

test_subject_undefined_for_wrong_issuer if {
	not subject with input as {"token": wrong_issuer_token} with opa.runtime as mock_runtime
}

test_is_admin_true_for_admin if {
	is_admin with input as {"token": valid_token} with opa.runtime as mock_runtime
}

test_is_admin_false_for_customer if {
	token := sign({"sub": "cust-1", "role": "customer", "iss": "internstore-gateway"}, "test-secret")
	not is_admin with input as {"token": token} with opa.runtime as mock_runtime
}

test_is_resource_owner_true_when_matching if {
	is_resource_owner
		with input as {"token": valid_token, "resource": {"owner": "admin-1"}}
		with opa.runtime as mock_runtime
}

test_is_resource_owner_false_when_mismatched if {
	not is_resource_owner
		with input as {"token": valid_token, "resource": {"owner": "someone-else"}}
		with opa.runtime as mock_runtime
}

# Services not yet migrated onto input.token (see common.rego's own
# comment) still send an already-decoded input.subject -- must keep
# working exactly as before until every service migrates.
test_subject_legacy_passthrough_when_no_token if {
	subject == {"role": "admin", "sub": "legacy-1"}
		with input as {"subject": {"role": "admin", "sub": "legacy-1"}}
}

test_is_admin_legacy_passthrough if {
	is_admin with input as {"subject": {"role": "admin", "sub": "legacy-1"}}
}

test_subject_undefined_with_neither_token_nor_subject if {
	not subject with input as {}
}
