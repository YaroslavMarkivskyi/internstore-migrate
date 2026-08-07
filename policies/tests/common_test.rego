package common

import future.keywords.if

test_is_admin_true_for_admin if {
	is_admin with input as {"subject": {"role": "admin", "sub": "admin-1"}}
}

test_is_admin_false_for_customer if {
	not is_admin with input as {"subject": {"role": "customer", "sub": "cust-1"}}
}

test_is_resource_owner_true_when_matching if {
	is_resource_owner with input as {"subject": {"sub": "cust-1"}, "resource": {"owner": "cust-1"}}
}

test_is_resource_owner_false_when_mismatched if {
	not is_resource_owner with input as {"subject": {"sub": "cust-1"}, "resource": {"owner": "cust-2"}}
}
