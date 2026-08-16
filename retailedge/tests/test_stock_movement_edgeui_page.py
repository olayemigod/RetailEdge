from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_API = APP_ROOT / "stock_movement_page.py"
PAGE_ROOT = APP_ROOT / "retailedge" / "page" / "stock_movement_history"
BUNDLE = APP_ROOT / "public" / "js" / "stock_movement_history.bundle.js"
COMPONENT = APP_ROOT / "public" / "js" / "stock_movement_history" / "StockMovementHistory.vue"
LEGACY_REPORT = (
	APP_ROOT
	/ "retailedge"
	/ "report"
	/ "retailedge_stock_movement_history"
	/ "retailedge_stock_movement_history.py"
)


class TestStockMovementEdgeUIPage(unittest.TestCase):
	def read(self, path: Path) -> str:
		return path.read_text(encoding="utf-8")

	def test_standard_page_and_bundle_files_exist(self):
		for path in (
			PAGE_API,
			PAGE_ROOT / "stock_movement_history.js",
			PAGE_ROOT / "stock_movement_history.json",
			PAGE_ROOT / "stock_movement_history.py",
			BUNDLE,
			COMPONENT,
		):
			self.assertTrue(path.exists(), path)

	def test_page_api_is_hard_bounded_before_display_filtering(self):
		source = self.read(PAGE_API)
		for contract in (
			"MAX_SCAN_ROWS = 1000",
			"DEFAULT_PAGE_SIZE = 50",
			"MAX_PAGE_SIZE = 100",
			"MAX_LINK_RESULTS = 20",
			"limit=MAX_SCAN_ROWS + 1",
			"if len(raw_rows) > MAX_SCAN_ROWS:",
			"Narrow the date range before loading Stock Movement History.",
		):
			self.assertIn(contract, source)

		cap_check = source.index("if len(raw_rows) > MAX_SCAN_ROWS:")
		zero_quantity_filter = source.index("if flt(row.actual_qty)")
		self.assertLess(cap_check, zero_quantity_filter)
		self.assertNotIn("limit_page_length=0", source)

	def test_page_api_reuses_existing_accounting_engine(self):
		source = self.read(PAGE_API)
		for helper in (
			"validate_filters",
			"resolve_warehouse_scope",
			"get_opening_balance",
			"split_opening_stock_reconciliations",
			"build_movement_rows",
			"apply_display_filters",
			"build_opening_balance_row",
			"get_report_summary",
		):
			self.assertIn(helper, source)

		legacy = self.read(LEGACY_REPORT)
		for accounting_contract in (
			"get_stock_balance",
			"Stock Ledger Entry",
			"apply_running_balances",
			"Stock Reconciliation",
		):
			self.assertIn(accounting_contract, legacy)

	def test_page_api_enforces_permissions_and_bounded_link_searches(self):
		source = self.read(PAGE_API)
		for contract in (
			"_assert_report_access(filters)",
			'frappe.has_permission("Stock Ledger Entry", "read")',
			'frappe.has_permission(doctype, "read", doc=name)',
			"branch_query(",
			"warehouse_query(",
			"limit=MAX_LINK_RESULTS",
		):
			self.assertIn(contract, source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_edgesuite_loader_uses_canonical_runtime_and_visible_failure(self):
		loader = self.read(PAGE_ROOT / "stock_movement_history.js")
		for contract in (
			'const EDGEUI_ASSET = "edgeui.bundle.js"',
			'const STOCK_MOVEMENT_ASSET = "stock_movement_history.bundle.js"',
			"await requireAsync(EDGEUI_ASSET)",
			"window.EdgeSuiteUI?.components",
			"await requireAsync(STOCK_MOVEMENT_ASSET)",
			"window.mountStockMovementHistory",
			"hideNativePageSidebar",
			"renderLoadError",
		):
			self.assertIn(contract, loader)
		self.assertLess(
			loader.index("await requireAsync(EDGEUI_ASSET)"),
			loader.index("await requireAsync(STOCK_MOVEMENT_ASSET)"),
		)

		bundle = self.read(BUNDLE)
		self.assertIn("window.EdgeSuiteUI", bundle)
		self.assertIn("createEdgeApp", bundle)
		self.assertNotIn("window.EdgeUI ||", bundle)

	def test_component_uses_smart_links_cascades_and_pagination(self):
		component = self.read(COMPONENT)
		for contract in (
			"EdgeLinkField",
			"search_stock_movement_options",
			"resolve_branch_warehouse_selection",
			"onBranchSelected",
			"onWarehouseSelected",
			"get_stock_movement_page",
			"pagination.has_previous",
			"pagination.has_next",
			"25 / page",
			"50 / page",
			"100 / page",
			":hideNativeSidebar=\"true\"",
		):
			self.assertIn(contract, component)
		self.assertNotIn("frappe.get_list", component)
		self.assertNotIn("frappe.get_all", component)

	def test_legacy_query_report_is_retained_as_fallback(self):
		self.assertTrue(LEGACY_REPORT.exists())
		legacy_js = LEGACY_REPORT.with_suffix(".js")
		legacy_json = LEGACY_REPORT.with_suffix(".json")
		self.assertTrue(legacy_js.exists())
		self.assertTrue(legacy_json.exists())
		self.assertIn(
			'frappe.query_reports["RetailEdge Stock Movement History"]',
			self.read(legacy_js),
		)


if __name__ == "__main__":
	unittest.main()
