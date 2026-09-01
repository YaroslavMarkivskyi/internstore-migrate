from mcp_gateway.authz import authorized_tools
from mcp_gateway.schema import TOOL_SPECS_BY_NAME

ALL = frozenset(TOOL_SPECS_BY_NAME)


def test_customer_and_guest_get_the_cart_and_customer_safe_reads_only():
    for role in ("customer", "guest"):
        allowed = authorized_tools(role, ALL)
        assert {"get_cart", "add_to_cart", "search_products", "search_help"} <= allowed
        assert not (allowed & {"get_visit_log", "get_pending_orders", "list_customer_orders", "get_stock_levels"})


def test_admin_gets_read_only_ops_tools_but_no_cart_writes():
    allowed = authorized_tools("admin", ALL)
    assert {"get_visit_log", "get_pending_orders", "get_active_incidents"} <= allowed
    assert not (allowed & {"add_to_cart", "remove_from_cart"})


def test_assistant_service_identity_gets_everything():
    assert authorized_tools("assistant", ALL) == ALL


def test_unknown_role_gets_nothing():
    assert authorized_tools("root", ALL) == frozenset()


def test_no_tier_ever_grants_a_tool_outside_the_catalogue():
    for role in ("customer", "guest", "admin", "assistant"):
        assert authorized_tools(role, ALL) <= ALL
