package payments

import future.keywords.if

test_admin_can_charge if {
	allow with input as {
		"subject": {"role": "admin", "sub": "checkout-workflow"},
		"action": "charge",
		"resource": {"type": "payment"},
	}
}

test_admin_can_refund if {
	allow with input as {
		"subject": {"role": "admin", "sub": "checkout-workflow"},
		"action": "refund",
		"resource": {"type": "payment"},
	}
}

test_customer_cannot_charge if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"action": "charge",
		"resource": {"type": "payment"},
	}
}
