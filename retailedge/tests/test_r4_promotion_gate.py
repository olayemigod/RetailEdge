from __future__ import annotations

from copy import deepcopy

from retailedge import edgesuite_ui, master_experience


PROMOTED_PAGE_TARGETS = {
	"Cashier Expense Review": "expense-review",
	"Cash Shift Verification": "cash-shift-verification",
	"Daily Sales Audit": "daily-sales-audit",
}


def _base_navigation_items() -> list[dict]:
	return [
		item
		for group in edgesuite_ui.NAVIGATION_GROUPS
		for item in group.get("items") or ()
	]


def _promoted_navigation_items() -> list[dict]:
	groups = deepcopy(list(edgesuite_ui.NAVIGATION_GROUPS))
	master_experience._promote_browser_approved_r4_pages(groups)
	return [item for group in groups for item in group.get("items") or ()]


def test_action_center_is_role_gated_edge_suite_navigation():
	items = _base_navigation_items()
	action_center = next(item for item in items if item.get("target") == "action-center")
	assert action_center["target_type"] == "Page"
	assert set(action_center.get("required_roles") or ()) == set(edgesuite_ui.ACTION_CENTER_ROLES)
	assert action_center.get("required_roles")


def test_browser_approved_r4_pages_are_promoted_in_live_context():
	items = _promoted_navigation_items()
	by_label = {item.get("label"): item for item in items}
	for label, target in PROMOTED_PAGE_TARGETS.items():
		item = by_label[label]
		assert item["target_type"] == "Page"
		assert item["target"] == target


def test_stock_movement_remains_qa_gated_on_native_report():
	items = _promoted_navigation_items()
	stock = next(item for item in items if item.get("label") == "Stock Movement History")
	assert stock["target_type"] == "Report"
	assert stock["target"] == "RetailEdge Stock Movement History"
	assert "Stock Movement History" not in master_experience.PROMOTED_R4_PAGE_TARGETS


def test_base_registry_keeps_native_fallbacks_available():
	items = _base_navigation_items()
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
