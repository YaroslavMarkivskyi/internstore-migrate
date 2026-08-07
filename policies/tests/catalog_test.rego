package catalog

import future.keywords.if

test_admin_can_create_product if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"action": "create",
		"resource": {"type": "product"},
	}
}

test_admin_can_update_product if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"action": "update",
		"resource": {"type": "product"},
	}
}

test_admin_can_create_category if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"action": "create",
		"resource": {"type": "category"},
	}
}

test_customer_cannot_create_product if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "create",
		"resource": {"type": "product"},
	}
}

test_customer_cannot_create_category if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "create",
		"resource": {"type": "category"},
	}
}
