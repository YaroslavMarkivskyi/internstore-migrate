package catalog

import future.keywords.if
import data.common

default allow := false

# Exported so AuthzClient.check can tell "no valid token" (subject
# undefined -> 401) apart from "valid token, wrong role" (subject
# present, allow false -> 403) in one call instead of two.
subject := common.subject

# Managing the catalog — creating/updating products and categories — is
# admin-only today (mirrors require_admin's previous behavior on these
# same call sites, see routers/products.py and routers/categories.py).
allow if {
	common.is_admin
}
