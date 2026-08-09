package inventory

import future.keywords.if
import data.common

default allow := false

# Stock mutation (creating/updating/deleting stocks and stock items) is
# admin-only today (mirrors require_admin's previous behavior on these same
# call sites, see routers/stocks.py).
allow if {
	common.is_admin
}
