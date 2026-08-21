package catalog

import future.keywords.if

# catalog is the first service migrated off passing a pre-decoded
# input.subject -- these mock data.common.subject directly (the verified
# result) rather than minting a real token per test case; common_test.rego
# owns testing the token-verification step itself.
test_admin_can_create_product if {
	allow with data.common.subject as {"role": "admin", "sub": "admin-1"}
		with input as {"action": "create", "resource": {"type": "product"}}
}

test_admin_can_update_product if {
	allow with data.common.subject as {"role": "admin", "sub": "admin-1"}
		with input as {"action": "update", "resource": {"type": "product"}}
}

test_admin_can_create_category if {
	allow with data.common.subject as {"role": "admin", "sub": "admin-1"}
		with input as {"action": "create", "resource": {"type": "category"}}
}

test_customer_cannot_create_product if {
	not allow with data.common.subject as {"role": "customer", "sub": "cust-1"}
		with input as {"action": "create", "resource": {"type": "product"}}
}

test_customer_cannot_create_category if {
	not allow with data.common.subject as {"role": "customer", "sub": "cust-1"}
		with input as {"action": "create", "resource": {"type": "category"}}
}

# No valid token at all (missing/forged/expired -- common.rego's own
# tests cover which) means data.common.subject is undefined, so allow
# must stay at its `default false`, not error.
test_no_verified_subject_denied if {
	not allow with input as {"action": "create", "resource": {"type": "product"}}
}

# `subject` (exported alongside `allow`) is what catalog-verify
# (internal-gate) reads to tell "no valid token" (401) apart from
# "valid token, wrong role" (403) in one round trip -- see
# services/internal-gate and nginx/internal-gate/catalog.conf.
test_subject_present_when_verified if {
	subject == {"role": "admin", "sub": "admin-1"}
		with data.common.subject as {"role": "admin", "sub": "admin-1"}
}

test_subject_undefined_when_not_verified if {
	not subject with input as {}
}
