package orders

import future.keywords.if

test_admin_can_view_any_order if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"action": "view",
		"resource": {"type": "order", "owner": "cust-2"},
	}
}

test_customer_can_view_own_order if {
	allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "view",
		"resource": {"type": "order", "owner": "cust-1"},
	}
}

test_customer_can_update_own_order if {
	allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "update",
		"resource": {"type": "order", "owner": "cust-1"},
	}
}

test_customer_cannot_view_others_order if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "view",
		"resource": {"type": "order", "owner": "cust-2"},
	}
}

test_customer_cannot_create_order if {
	# Customers check out through the same guest-shaped create flow, but
	# this policy only grants "create" to guests explicitly — a customer
	# creating an order goes through the ordinary checkout call site, which
	# doesn't consult this rule at all today.
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "create",
		"resource": {"type": "order"},
	}
}

test_guest_can_create_order if {
	allow with input as {
		"subject": {"role": "guest", "sub": "guest-1"},
		"action": "create",
		"resource": {"type": "order"},
	}
}

test_guest_cannot_view_order if {
	not allow with input as {
		"subject": {"role": "guest", "sub": "guest-1"},
		"action": "view",
		"resource": {"type": "order", "owner": "guest-1"},
	}
}
