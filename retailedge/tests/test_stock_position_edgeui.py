from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge import stock_position

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / "stock_position.py"
BUNDLE = APP_ROOT / "public" / "js" / "stock_position.bundle.js"
COMPONENT = APP_ROOT / "public" / "js" / "stock_position" / "StockPositionReport.vue"
PAGE_ROOT = APP_ROOT / "retailedge" / "page" / "stock_position"


class TestStockPositionEdgeUI(unittest.TestCase):
	def read(self, path: Path) -> str:
		return path.read_text(encoding="utf-8")

	def test_stock_position_page_and_bundle_exist(self):
		for path in (
			BACKEND,
			BUNDLE,
			COMPONENT,
			PAGE_ROOT / "stock_position.js",
			PAGE_ROOT / "stock_position.json",
			PAGE_ROOT / "stock_position.py",
		):
			self.assertTrue(path.exists(), path)

	def test_page_is_stock_and_retailedge_role_gated(self):
		payload = json.loads(self.read(PAGE_ROOT / "stock_position.json"))
		self.assertEqual(payload["name"], "stock-position")
		self.assertEqual(payload["title"], "Stock Position")
		roles = {entry["role"] for entry in payload["roles"]}
		for role in ("Stock User", "Stock Manager", "RetailEdge Manager", "RetailEdge Branch Manager", "RetailEdge Auditor"):
			self.assertIn(role, roles)

	def test_bin_source_is_permission_aware_and_hard_bounded(self):
		source = self.read(BACKEND)
		for contract in (
			"MAX_WAREHOUSE_SCOPE = 500",
			"MAX_BIN_SCAN_ROWS = 10000",
			"MAX_ITEM_SCOPE = 5000",
			"MAX_LINK_RESULTS = 20",
			'frappe.has_permission("Bin", "read")',
			'frappe.get_list(\n\t\t"Bin"',
			"limit=MAX_BIN_SCAN_ROWS + 1",
			"get_operational_branch_scope",
			"_assert_branch_read_scope",
			"_branch_scope_warehouses",
			"get_branch_warehouses",
		):
			self.assertIn(contract, source)
		self.assertNotIn("validate_user_branch_access", source)
		self.assertNotIn("get_user_allowed_branches", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit()", source)
		self.assertNotIn("frappe.db.sql", source)

	def test_restricted_explicit_branch_outside_assignments_fails_closed(self):
		filters = stock_position.frappe._dict(company="Scope Co", branch="Branch B")
		with (
			patch.object(
				stock_position,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"], "source": "branch_assignment"},
			),
			patch.object(stock_position.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				stock_position._resolve_warehouse_scope(filters)

	def test_restricted_blank_branch_aggregates_only_assignment_warehouses(self):
		filters = stock_position.frappe._dict(company="Scope Co")
		with (
			patch.object(
				stock_position,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch A", "Branch B"],
					"source": "branch_assignment",
				},
			),
			patch.object(
				stock_position,
				"get_branch_warehouses",
				side_effect=lambda company, branch: [f"{branch} Warehouse"],
			),
			patch.object(
				stock_position.frappe,
				"get_list",
				return_value=["Branch A Warehouse", "Branch B Warehouse"],
			),
		):
			warehouses = stock_position._resolve_warehouse_scope(filters)

		self.assertEqual(warehouses, ["Branch A Warehouse", "Branch B Warehouse"])

	def test_restricted_zero_active_branches_fails_closed(self):
		filters = stock_position.frappe._dict(company="Scope Co")
		with (
			patch.object(
				stock_position,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": [], "source": "branch_assignment"},
			),
			patch.object(stock_position.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				stock_position._resolve_warehouse_scope(filters)

	def test_explicit_warehouse_branch_is_checked_against_assignment_scope(self):
		filters = stock_position.frappe._dict(company="Scope Co", warehouse="Branch B Warehouse")
		with (
			patch.object(
				stock_position,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"], "source": "branch_assignment"},
			),
			patch.object(stock_position, "_assert_named_read"),
			patch.object(stock_position.frappe.db, "get_value", return_value=("Scope Co", 0)),
			patch.object(
				stock_position,
				"resolve_branch_from_warehouse",
				return_value={"branch": "Branch B", "company": "Scope Co"},
			),
			patch.object(stock_position.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				stock_position._resolve_warehouse_scope(filters)

	def test_unrestricted_blank_branch_retains_company_wide_scope(self):
		filters = stock_position.frappe._dict(company="Scope Co")
		with (
			patch.object(
				stock_position,
				"get_operational_branch_scope",
				return_value={"restricted": False, "allowed_branches": [], "source": "global"},
			),
			patch.object(
				stock_position,
				"_all_company_warehouses",
				return_value=["Warehouse A", "Warehouse B"],
			) as all_company,
			patch.object(
				stock_position.frappe,
				"get_list",
				return_value=["Warehouse A", "Warehouse B"],
			),
		):
			warehouses = stock_position._resolve_warehouse_scope(filters)

		self.assertEqual(warehouses, ["Warehouse A", "Warehouse B"])
		all_company.assert_called_once_with("Scope Co")

	def test_cost_visibility_uses_existing_retailedge_policy_and_avoids_fetch_when_hidden(self):
		source = inspect.getsource(stock_position._build_stock_position_dataset)
		self.assertIn("show_costs = not should_hide_cost_price()", source)
		self.assertIn("fields = list(_BASE_BIN_FIELDS)", source)
		self.assertIn("if show_costs:\n\t\tfields.extend(_COST_BIN_FIELDS)", source)
		self.assertLess(source.index("if show_costs:\n\t\tfields.extend(_COST_BIN_FIELDS)"), source.index('frappe.get_list(\n\t\t"Bin"'))
		module_source = self.read(BACKEND)
		self.assertIn('from retailedge.cost_visibility import should_hide_cost_price', module_source)
		self.assertEqual(stock_position._COST_BIN_FIELDS, ("valuation_rate", "stock_value"))

	def test_cost_columns_and_summary_are_removed_when_hidden(self):
		hidden_columns = {column["fieldname"] for column in stock_position._columns("NGN", show_costs=False)}
		visible_columns = {column["fieldname"] for column in stock_position._columns("NGN", show_costs=True)}
		self.assertNotIn("valuation_rate", hidden_columns)
		self.assertNotIn("stock_value", hidden_columns)
		self.assertIn("valuation_rate", visible_columns)
		self.assertIn("stock_value", visible_columns)

		rows = [{"actual_qty": 5, "available_qty": 3, "stock_value": 2500}]
		hidden_labels = {card["label"] for card in stock_position._summary(rows, show_costs=False)}
		visible_labels = {card["label"] for card in stock_position._summary(rows, show_costs=True)}
		self.assertNotIn("Stock Value", hidden_labels)
		self.assertIn("Stock Value", visible_labels)

	def test_stock_status_logic_preserves_negative_and_reserved_exceptions(self):
		self.assertEqual(stock_position._row_stock_status({"actual_qty": -1, "available_qty": -1}), "Negative")
		self.assertEqual(stock_position._row_stock_status({"actual_qty": 0, "available_qty": 0}), "Out of Stock")
		self.assertEqual(stock_position._row_stock_status({"actual_qty": 5, "available_qty": 0}), "Fully Reserved")
		self.assertEqual(stock_position._row_stock_status({"actual_qty": 5, "available_qty": 2}), "Available")
		self.assertTrue(stock_position._matches_stock_status({"actual_qty": 5, "stock_status": "Available"}, "In Stock"))

	def test_frontend_uses_smart_cascades_shared_export_and_pagination(self):
		component = self.read(COMPONENT)
		for contract in (
			"EdgeLinkField",
			"EdgeExportMenu",
			":loadDataset=\"loadExportDataset\"",
			"window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)",
			"this.reportProvider?.export",
			"search_stock_position_options",
			"resolve_branch_warehouse_selection",
			':pageSizes="[25, 50, 100]"',
			":hideNativeSidebar=\"true\"",
			"Cost values hidden by RetailEdge settings",
		):
			self.assertIn(contract, component)
		for forbidden in ("new Blob", "createObjectURL", "text/csv", "application/vnd", "window.print"):
			self.assertNotIn(forbidden, component)

	def test_filter_layout_uses_available_width_responsively(self):
		component = self.read(COMPONENT)
		for contract in (
			".stock-position-filter-grid",
			"grid-template-columns: repeat(4, minmax(0, 1fr))",
			"grid-template-columns: repeat(3, minmax(0, 1fr))",
			"grid-template-columns: repeat(2, minmax(0, 1fr))",
			"grid-template-columns: 1fr",
			"width: 100%",
		):
			self.assertIn(contract, component)

	def test_loader_uses_canonical_edgesuite_runtime_and_hides_native_sidebar(self):
		loader = self.read(PAGE_ROOT / "stock_position.js")
		for contract in (
			'const EDGEUI_ASSET = "edgeui.bundle.js"',
			'const STOCK_POSITION_ASSET = "stock_position.bundle.js"',
			"await requireAsync(EDGEUI_ASSET)",
			"window.EdgeSuiteUI?.components",
			"await requireAsync(STOCK_POSITION_ASSET)",
			"window.mountStockPosition",
			"hideNativePageSidebar",
			"renderLoadError",
		):
			self.assertIn(contract, loader)
		self.assertLess(loader.index("await requireAsync(EDGEUI_ASSET)"), loader.index("await requireAsync(STOCK_POSITION_ASSET)"))

		bundle = self.read(BUNDLE)
		self.assertIn("window.EdgeSuiteUI", bundle)
		self.assertIn("createEdgeApp", bundle)
		self.assertNotIn("window.EdgeUI ||", bundle)


if __name__ == "__main__":
	unittest.main()
