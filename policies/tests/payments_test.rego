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

test_subject_present_when_verified if {
	subject == {"role": "admin", "sub": "checkout-workflow"}
		with data.common.subject as {"role": "admin", "sub": "checkout-workflow"}
}

test_subject_undefined_when_not_verified if {
	not subject with input as {}
}
