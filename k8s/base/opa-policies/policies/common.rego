package common

import future.keywords.if

# True when the calling subject holds the "admin" role. Every domain
# policy in this directory treats admin as "can do anything" — this rule
# is the single place that fact is encoded, so it only needs auditing once.
is_admin if {
	input.subject.role == "admin"
}

# True when the resource being acted on is owned by the calling subject
# (e.g. an order's owner_id matching the customer's own sub). Domain
# policies combine this with their own action/resource.type checks —
# this rule only knows about the ownership relationship itself.
is_resource_owner if {
	input.resource.owner == input.subject.sub
}
