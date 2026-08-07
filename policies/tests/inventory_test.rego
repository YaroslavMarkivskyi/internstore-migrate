package inventory

import future.keywords.if

test_admin_can_mutate_stock if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"action": "update",
		"resource": {"type": "stock"},
	}
}

test_admin_can_mutate_stock_item if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"action": "create",
		"resource": {"type": "stock_item"},
	}
}

test_customer_cannot_mutate_stock if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "update",
		"resource": {"type": "stock"},
	}
}
