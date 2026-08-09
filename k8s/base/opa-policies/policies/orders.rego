package orders

import future.keywords.if
import data.common

default allow := false

# Admins can do anything in Orders
allow if {
	common.is_admin
}

# Customers can view/update only their own orders
allow if {
	input.action in ["view", "update"]
	input.resource.type == "order"
	input.subject.role == "customer"
	common.is_resource_owner
}

# Guests can only create orders (checkout) and view their own via session_id
allow if {
	input.action == "create"
	input.resource.type == "order"
	input.subject.role == "guest"
}
