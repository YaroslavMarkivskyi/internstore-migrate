package orders

import future.keywords.if

test_admin_allowed_regardless_of_required_role if {
	allow with input as {
		"subject": {"role": "admin", "sub": "checkout-workflow"},
		"required_role": "admin",
	}
}

test_customer_denied_for_admin_only_route if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"required_role": "admin",
	}
}

test_assistant_allowed_for_admin_or_assistant_route if {
	allow with input as {
		"subject": {"role": "assistant", "sub": "ai-assistant"},
		"required_role": "admin_or_assistant",
	}
}

test_customer_denied_for_admin_or_assistant_route if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"required_role": "admin_or_assistant",
	}
}

test_customer_can_checkout if {
	allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"required_role": "any",
	}
}

test_guest_can_checkout if {
	allow with input as {
		"subject": {"role": "guest", "sub": "guest-1"},
		"required_role": "any",
	}
}

test_subject_present_when_verified if {
	subject == {"role": "admin", "sub": "checkout-workflow"}
		with data.common.subject as {"role": "admin", "sub": "checkout-workflow"}
}

test_subject_undefined_when_not_verified if {
	not subject with input as {}
}
