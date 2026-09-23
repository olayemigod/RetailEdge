from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DESTINATION_PAGES = (
    "retailedge/page/expense_register/expense_register.js",
    "retailedge/page/customer_receivables/customer_receivables.js",
    "retailedge/page/supplier_payables/supplier_payables.js",
    "retailedge/page/stock_position/stock_position.js",
    "retailedge/page/cash_movement/cash_movement.js",
    "retailedge/page/branch_performance_dashboard/branch_performance_dashboard.js",
    "retailedge/page/sales_by_item/sales_by_item.js",
    "retailedge/page/sales_invoice_register/sales_invoice_register.js",
)


def test_cached_business_hub_destinations_reconsume_fresh_handoffs_on_page_show():
    for relative in DESTINATION_PAGES:
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "wrapper._retailedgeVueApp = await" in source, relative
        assert "function refreshPendingBusinessHubHandoff(wrapper)" in source, relative
        assert "retailedge_business_hub_handoff" in source, relative
        assert "retailedge_business_hub_target" in source, relative
        assert "String(routeOptions.retailedge_business_hub_target || \"\") !== PAGE_ROUTE" in source, relative
        assert "wrapper._retailedgePageHasShown" in source, relative
        mounted_tail = source.split("wrapper._retailedgeVueApp = await", 1)[1]
        assert "wrapper._retailedgePageHasShown = true;" in mounted_tail, relative
        assert "bindBusinessHubHandoffRouteRefresh(wrapper);" in mounted_tail, relative
        assert 'document.addEventListener("page-change", refresh)' in source, relative
        assert 'frappe.router?.on?.("change", refresh)' in source, relative
        assert "component.fetchMetadata()" in source, relative
        assert "refreshPendingBusinessHubHandoff(wrapper);" in source, relative


def test_handoff_refresh_is_guarded_and_does_not_remount_cached_destination():
    for relative in DESTINATION_PAGES:
        source = (ROOT / relative).read_text(encoding="utf-8")
        helper = source.split("function refreshPendingBusinessHubHandoff(wrapper)", 1)[1].split(
            "frappe.pages[PAGE_ROUTE].on_page_load", 1
        )[0]
        assert "mount" not in helper.lower(), relative
        assert "frappe.route_options || {}" in helper, relative
        assert "window.__retailedgeBusinessHubRouteHandoff || {}" in helper, relative
        assert "routeOptionMatches" in helper, relative
        assert "handoffMatches" in helper, relative
        assert "Date.now() - Number(handoff.createdAt || 0) <= 60_000" in helper, relative
        assert "typeof component.fetchMetadata !== \"function\"" in helper, relative
