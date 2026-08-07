package security

import future.keywords.if

test_admin_can_manage_users if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"action": "create",
		"resource": {"type": "user"},
	}
}

test_admin_can_view_visit_log if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"action": "view",
		"resource": {"type": "visit_log"},
	}
}

test_customer_cannot_manage_users if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "create",
		"resource": {"type": "user"},
	}
}

test_customer_cannot_view_visit_log if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "view",
		"resource": {"type": "visit_log"},
	}
}
