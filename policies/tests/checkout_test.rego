package checkout

import future.keywords.if

test_admin_can_create_order_from_workflow if {
	allow with input as {
		"subject": {"role": "admin", "sub": "checkout-workflow"},
		"action": "create_order",
		"resource": {"type": "order"},
	}
}

test_admin_can_update_order_status_from_workflow if {
	allow with input as {
		"subject": {"role": "admin", "sub": "checkout-workflow"},
		"action": "update_order_status",
		"resource": {"type": "order"},
	}
}

test_customer_can_checkout if {
	allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "checkout",
		"resource": {"type": "cart"},
	}
}

test_guest_can_checkout if {
	allow with input as {
		"subject": {"role": "guest", "sub": "guest-1"},
		"action": "checkout",
		"resource": {"type": "cart"},
	}
}

test_customer_cannot_create_order_from_workflow if {
	# Only checkout-workflow's own admin-role identity may call the
	# internal create_order/update_order_status endpoints directly.
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "create_order",
		"resource": {"type": "order"},
	}
}
