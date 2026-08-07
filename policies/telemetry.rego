package telemetry

import future.keywords.if
import data.common

default allow := false

# No Telemetry endpoint has been migrated to OPA yet — STR-140's initial
# rollout is Catalog/Orders/Inventory/Security only (see the ticket's
# explicit scope). This policy exists so Telemetry's sidecar has something
# to load and is ready for a follow-up ticket to wire real call sites
# against, same admin-can-do-anything baseline as every other domain
# policy in the meantime.
allow if {
	common.is_admin
}
