from __future__ import annotations

from retailedge import edgesuite_ui


QA_GATED_PAGE_TARGETS = {
	"stock-movement-history",
	"expense-review",
	"cash-shift-verification",
	"daily-sales-audit",
}


def _navigation_items() -> list[dict]:
	return [
		item
		for group in edgesuite_ui.NAVIGATION_GROUPS
		for item in group.get("items") or ()
	]


def test_action_center_is_role_gated_edge_suite_navigation():
	items = _navigation_items()
	action_center = next(item for item in items if item.get("target") == "action-center")
	assert action_center["target_type"] == "Page"
	assert set(action_center.get("required_roles") or ()) == set(edgesuite_ui.ACTION_CENTER_ROLES)
	assert action_center.get("required_roles")


def test_r4_preview_pages_remain_unpromoted_until_browser_qa():
	items = _navigation_items()
	page_targets = {
		item.get("target")
		for item in items
		if item.get("target_type") == "Page"
	}
	assert QA_GATED_PAGE_TARGETS.isdisjoint(page_targets)


def test_r4_preview_fallbacks_remain_explicit():
	items = _navigation_items()
	by_label = {item.get("label"): item for item in items}

	stock = by_label["Stock Movement History"]
	assert stock["target_type"] == "Report"
	assert stock["target"] == "RetailEdge Stock Movement History"

	expense = by_label["Cashier Expense Review"]
	assert expense["target_type"] == "Report"
	assert expense["target"] == "RetailEdge Cashier Expense Review"

	cash = by_label["Cash Shift Verification"]
	assert cash["target_type"] == "Report"
	assert cash["target"] == "RetailEdge Cash Shift Verification"

	daily_sales = by_label["Daily Sales Audit"]
	assert daily_sales["target_type"] == "DocType"
	assert daily_sales["target"] == "RetailEdge Daily Sales Audit"
