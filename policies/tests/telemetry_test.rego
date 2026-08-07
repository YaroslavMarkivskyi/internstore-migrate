package telemetry

import future.keywords.if

test_admin_allowed if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"action": "view",
		"resource": {"type": "reading"},
	}
}

test_customer_denied if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "view",
		"resource": {"type": "reading"},
	}
}
