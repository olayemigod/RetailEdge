from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

from retailedge import master_experience


ROOT = Path(__file__).resolve().parents[1]
MASTER_EXPERIENCE = ROOT / "master_experience.py"
BUSINESS_HUB = ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue"
GUIDED_UTILS = ROOT / "public/js/retailedge_business_hub/guidedEntryUtils.js"
LEGACY_STOCK_REPORT = (
	ROOT
	/ "retailedge/report/retailedge_stock_movement_history/retailedge_stock_movement_history.py"
)
STOCK_PAGE = ROOT / "retailedge/page/stock_movement_history/stock_movement_history.json"
DOC = ROOT.parent / "docs/rir2f3f42_readiness_hardening_closure_audit.md"


def _stock_groups():
	return [
		{
			"key": "stock",
			"items": [
				{
					"label": "Stock Movement History",
					"target_type": "Report",
					"target": "RetailEdge Stock Movement History",
					"icon": "report",
				},
				{
					"label": "Stock Position",
					"target_type": "Page",
					"target": "stock-position",
					"icon": "report",
				},
			],
		}
	]


def test_stock_movement_history_promotes_existing_report_item_only_when_page_is_permitted():
	groups = _stock_groups()
	with patch.object(master_experience, "_can_open_page", return_value=True):
		master_experience._promote_stock_movement_history(groups)

	item = groups[0]["items"][0]
	assert item["label"] == "Stock Movement History"
	assert item["target_type"] == "Page"
	assert item["target"] == "stock-movement-history"
	assert groups[0]["items"][1]["target"] == "stock-position"


def test_stock_movement_history_preserves_legacy_report_when_page_is_unavailable():
	groups = _stock_groups()
	with patch.object(master_experience, "_can_open_page", return_value=False):
		master_experience._promote_stock_movement_history(groups)

	item = groups[0]["items"][0]
	assert item["target_type"] == "Report"
	assert item["target"] == "RetailEdge Stock Movement History"


def test_stock_movement_promotion_is_exact_and_does_not_rewrite_other_reports():
	source = inspect.getsource(master_experience._promote_stock_movement_history)
	assert 'group.get("key") != "stock"' in source
	assert "STOCK_MOVEMENT_HISTORY_REPORT_TARGET" in source
	assert "STOCK_MOVEMENT_HISTORY_PAGE_TARGET" in source
	assert "_can_open_page(STOCK_MOVEMENT_HISTORY_PAGE_TARGET)" in source
	assert "append(" not in source
	assert "insert(" not in source


def test_final_business_hub_context_applies_stock_movement_ownership():
	source = inspect.getsource(master_experience.get_retailedge_business_hub_context)
	assert "_promote_stock_movement_history(navigation_groups)" in source
	assert 'feature_flags["stock_movement_history_ownership"] = "edgesuite_page"' in source


def test_legacy_stock_report_and_edgesuite_page_are_both_retained():
	assert LEGACY_STOCK_REPORT.exists()
	assert STOCK_PAGE.exists()


def test_business_hub_maps_master_quick_actions_to_fixed_doctypes():
	source = BUSINESS_HUB.read_text(encoding="utf-8")
	assert "QUICK_ENTRY_MASTER_ACTIONS" in source
	for key, doctype in (
		("new-customer", "Customer"),
		("new-supplier", "Supplier"),
		("new-item", "Item"),
	):
		assert f'"{key}": "{doctype}"' in source
	assert "openQuickEntryMaster" in source
	assert "QUICK_ENTRY_MASTER_ACTIONS[action.key]" in source


def test_master_quick_entry_does_not_depend_on_native_desk_capability():
	source = BUSINESS_HUB.read_text(encoding="utf-8")
	mapping_index = source.index("QUICK_ENTRY_MASTER_ACTIONS[action.key]")
	native_block_index = source.index("if (!this.nativeFallbackEnabled)", mapping_index)
	assert mapping_index < native_block_index
	block = source[mapping_index:native_block_index]
	assert "openQuickEntryMaster" in block
	assert "action.doctype" not in block


def test_unknown_native_actions_still_fail_closed_without_native_desk():
	source = BUSINESS_HUB.read_text(encoding="utf-8")
	assert 'if (!this.nativeFallbackEnabled)' in source
	assert "This account is limited to EdgeSuite operational pages." in source
	assert "frappe.new_doc(action.doctype)" in source


def test_guided_entry_utils_exposes_blank_permission_aware_quick_entry_helper():
	source = GUIDED_UTILS.read_text(encoding="utf-8")
	assert "export function openQuickEntryMaster(doctype, initialValues = {})" in source
	assert "frappe.model.get_new_doc(doctype" in source
	assert "frappe.ui.form" in source
	assert ".make_quick_entry(" in source
	assert "quickCreateMaster" in source
	assert "return openQuickEntryMaster(doctype" in source


def test_closure_contract_keeps_intentional_advanced_routes_out_of_scope():
	source = DOC.read_text(encoding="utf-8")
	for phrase in (
		"Stock Entry submit ownership",
		"rebuilding ERPNext detailed financial reports",
		"replacing Payment Reconciliation or Payment Order",
		"building Customer/Supplier/Item management pages",
	):
		assert phrase in source


def test_f3f42_does_not_change_accounting_or_stock_backend_truth():
	source = MASTER_EXPERIENCE.read_text(encoding="utf-8")
	assert "frappe.db.commit" not in inspect.getsource(master_experience._promote_stock_movement_history)
	assert "ignore_permissions" not in inspect.getsource(master_experience._promote_stock_movement_history)
	assert "Stock Ledger Entry" not in inspect.getsource(master_experience._promote_stock_movement_history)
	assert "GL Entry" not in inspect.getsource(master_experience._promote_stock_movement_history)
