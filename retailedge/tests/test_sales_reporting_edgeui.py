from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path

from retailedge import sales_reporting

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / "sales_reporting.py"
BUNDLE = APP_ROOT / "public" / "js" / "sales_reporting.bundle.js"
COMPONENT = APP_ROOT / "public" / "js" / "sales_reporting" / "SalesReportingPage.vue"
SALES_BY_ITEM_PAGE = APP_ROOT / "retailedge" / "page" / "sales_by_item"
INVOICE_REGISTER_PAGE = APP_ROOT / "retailedge" / "page" / "sales_invoice_register"


class TestSalesReportingEdgeUI(unittest.TestCase):
	def read(self, path: Path) -> str:
		return path.read_text(encoding="utf-8")

	def test_sales_reporting_pages_and_shared_bundle_exist(self):
		for path in (
			BACKEND,
			BUNDLE,
			COMPONENT,
			SALES_BY_ITEM_PAGE / "sales_by_item.js",
			SALES_BY_ITEM_PAGE / "sales_by_item.json",
			SALES_BY_ITEM_PAGE / "sales_by_item.py",
			INVOICE_REGISTER_PAGE / "sales_invoice_register.js",
			INVOICE_REGISTER_PAGE / "sales_invoice_register.json",
			INVOICE_REGISTER_PAGE / "sales_invoice_register.py",
		):
			self.assertTrue(path.exists(), path)

	def test_pages_are_role_gated_and_use_business_titles(self):
		cases = (
			(SALES_BY_ITEM_PAGE / "sales_by_item.json", "sales-by-item", "Sales by Item"),
			(INVOICE_REGISTER_PAGE / "sales_invoice_register.json", "sales-invoice-register", "Sales Invoice Register"),
		)
		for path, name, title in cases:
			payload = json.loads(self.read(path))
			self.assertEqual(payload["name"], name)
			self.assertEqual(payload["title"], title)
			roles = {entry["role"] for entry in payload["roles"]}
			self.assertIn("Sales User", roles)
			self.assertIn("Sales Manager", roles)
			self.assertIn("RetailEdge Branch Manager", roles)
			self.assertIn("RetailEdge Auditor", roles)

	def test_backend_is_submitted_invoice_based_permission_aware_and_bounded(self):
		source = self.read(BACKEND)
		for contract in (
			"MAX_INVOICE_SCAN_ROWS = 2000",
			"MAX_ITEM_SCAN_ROWS = 10000",
			"MAX_SALES_TEAM_ROWS = 5000",
			"MAX_PAGE_SIZE = 100",
			"MAX_LINK_RESULTS = 20",
			'"docstatus": 1',
			'frappe.get_list(\n\t\t"Sales Invoice"',
			"limit=MAX_INVOICE_SCAN_ROWS + 1",
			'"parent": ["in", invoice_names]',
			"limit=MAX_ITEM_SCAN_ROWS + 1",
			"validate_user_branch_access",
			"frappe.has_permission(\"Sales Invoice\", \"read\")",
		):
			self.assertIn(contract, source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit()", source)
		self.assertNotIn("frappe.db.sql", source)

	def test_child_rows_are_only_read_after_permitted_parent_names_are_known(self):
		source = inspect.getsource(sales_reporting._build_sales_by_item_dataset)
		self.assertLess(source.index("_get_permitted_invoice_headers"), source.index("_get_invoice_items"))
		item_source = inspect.getsource(sales_reporting._get_invoice_items)
		self.assertIn('"parent": ["in", invoice_names]', item_source)
		self.assertIn('"parenttype": "Sales Invoice"', item_source)

	def test_sales_by_item_handles_returns_without_exposing_cost(self):
		self.assertEqual(sales_reporting._signed_for_return(125, True), -125)
		self.assertEqual(sales_reporting._signed_for_return(-125, True), -125)
		self.assertEqual(sales_reporting._signed_for_return(125, False), 125)
		source = self.read(BACKEND)
		for forbidden in ("valuation_rate", "buying_rate", "purchase_rate", "gross_profit", "cost_price"):
			self.assertNotIn(forbidden, source)
		for visible in ("sold_qty", "returned_qty", "net_qty", "sales_value", "returns_value", "net_sales"):
			self.assertIn(visible, source)

	def test_frontend_uses_shared_export_and_no_product_file_generator(self):
		component = self.read(COMPONENT)
		for contract in (
			"EdgeExportMenu",
			":loadDataset=\"loadExportDataset\"",
			"get_sales_by_item_export",
			"get_sales_invoice_register_export",
			"search_sales_reporting_options",
			"resolve_branch_warehouse_selection",
			"25 / page",
			"50 / page",
			"100 / page",
			":hideNativeSidebar=\"true\"",
		):
			self.assertIn(contract, component)
		for forbidden in ("new Blob", "createObjectURL", "text/csv", "application/vnd", "window.print"):
			self.assertNotIn(forbidden, component)

	def test_filter_layout_uses_available_width_responsively(self):
		component = self.read(COMPONENT)
		for contract in (
			"grid-template-columns: repeat(4, minmax(0, 1fr))",
			"grid-template-columns: repeat(3, minmax(0, 1fr))",
			"grid-template-columns: repeat(2, minmax(0, 1fr))",
			"grid-template-columns: 1fr",
			":deep(.edge-filter-bar__fields)",
			"width: 100%",
		):
			self.assertIn(contract, component)

	def test_loaders_use_canonical_edgesuite_runtime_and_hide_native_sidebar(self):
		for path in (
			SALES_BY_ITEM_PAGE / "sales_by_item.js",
			INVOICE_REGISTER_PAGE / "sales_invoice_register.js",
		):
			loader = self.read(path)
			for contract in (
				'const EDGEUI_ASSET = "edgeui.bundle.js"',
				'const SALES_REPORTING_ASSET = "sales_reporting.bundle.js"',
				"await requireAsync(EDGEUI_ASSET)",
				"window.EdgeSuiteUI?.components",
				"await requireAsync(SALES_REPORTING_ASSET)",
				"window.mountSalesReportingPage",
				"hideNativePageSidebar",
				"renderLoadError",
			):
				self.assertIn(contract, loader)
			self.assertLess(loader.index("await requireAsync(EDGEUI_ASSET)"), loader.index("await requireAsync(SALES_REPORTING_ASSET)"))

		bundle = self.read(BUNDLE)
		self.assertIn("window.EdgeSuiteUI", bundle)
		self.assertIn("createEdgeApp", bundle)
		self.assertNotIn("window.EdgeUI ||", bundle)


if __name__ == "__main__":
	unittest.main()
