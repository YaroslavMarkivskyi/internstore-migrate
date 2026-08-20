package telemetry

import future.keywords.if

test_admin_allowed if {
	allow with input as {"subject": {"role": "admin", "sub": "admin-1"}}
}

test_customer_denied if {
	not allow with input as {"subject": {"role": "customer", "sub": "cust-1"}}
}

test_subject_present_when_verified if {
	subject == {"role": "admin", "sub": "admin-1"}
		with data.common.subject as {"role": "admin", "sub": "admin-1"}
}

test_subject_undefined_when_not_verified if {
	not subject with input as {}
}
