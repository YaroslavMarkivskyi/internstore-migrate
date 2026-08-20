package chat

import future.keywords.if

test_admin_allowed_for_admin_only_route if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"required_role": "admin",
	}
}

test_admin_allowed_for_admin_or_assistant_route if {
	allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"required_role": "admin_or_assistant",
	}
}

# Deliberately not a blanket "admin can do anything" -- this route is
# assistant-*only* (mirrors require_assistant's previous behavior, which
# rejected admin too).
test_admin_denied_for_assistant_only_route if {
	not allow with input as {
		"subject": {"role": "admin", "sub": "admin-1"},
		"required_role": "assistant",
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

test_assistant_allowed_for_assistant_only_route if {
	allow with input as {
		"subject": {"role": "assistant", "sub": "ai-assistant"},
		"required_role": "assistant",
	}
}

test_customer_denied_for_assistant_only_route if {
	not allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"required_role": "assistant",
	}
}

test_customer_allowed_for_any_authenticated_route if {
	allow with input as {
		"subject": {"role": "customer", "sub": "cust-1"},
		"required_role": "any",
	}
}

test_guest_allowed_for_any_authenticated_route if {
	allow with input as {
		"subject": {"role": "guest", "sub": "guest-1"},
		"required_role": "any",
	}
}

test_subject_present_when_verified if {
	subject == {"role": "admin", "sub": "admin-1"}
		with data.common.subject as {"role": "admin", "sub": "admin-1"}
}

test_subject_undefined_when_not_verified if {
	not subject with input as {}
}
