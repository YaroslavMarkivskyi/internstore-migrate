package inventory

import future.keywords.if

test_admin_can_mutate_stock if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"required_role": "admin",
	}
}

test_admin_can_mutate_stock_item if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"required_role": "admin",
	}
}

test_customer_cannot_mutate_stock if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"required_role": "admin",
	}
}

# check-availability/reserve/release: any authenticated identity is enough,
# not just admin (mirrors get_internal_claims-only, no require_admin, on
# these three routes -- see routers/stocks.py).
test_customer_can_use_identity_only_route if {
	allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"required_role": "any",
	}
}

test_admin_can_use_identity_only_route if {
	allow with input as {
		"subject": {"role": "admin", "sub": "checkout-workflow"},
		"required_role": "any",
	}
}

test_missing_required_role_defaults_to_admin_only if {
	not allow with input as {"subject": {"role": "customer", "sub": "cust-1"}}
}

test_subject_present_when_verified if {
	subject == {"role": "admin", "sub": "checkout-workflow"}
		with data.common.subject as {"role": "admin", "sub": "checkout-workflow"}
}

test_subject_undefined_when_not_verified if {
	not subject with input as {}
}
