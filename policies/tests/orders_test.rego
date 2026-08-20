package orders

import future.keywords.if

# --- Resource-level ownership checks (routers/orders.py's get_order) ---

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

# --- Route-level gate tiers (orders-verify/internal-gate, previously
# package "checkout" -- see nginx/internal-gate/orders.conf) ---

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
