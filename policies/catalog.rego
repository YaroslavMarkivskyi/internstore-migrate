package catalog

import future.keywords.if
import data.common

default allow := false

# Managing the catalog — creating/updating products and categories — is
# admin-only today (mirrors require_admin's previous behavior on these
# same call sites, see routers/products.py and routers/categories.py).
allow if {
	common.is_admin
}
