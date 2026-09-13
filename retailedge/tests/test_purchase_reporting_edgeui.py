from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path

from retailedge import purchase_reporting

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / "purchase_reporting.py"
BUNDLE = APP_ROOT / "public" / "js" / "purchase_reporting.bundle.js"
COMPONENT = APP_ROOT / "public" / "js" / "purchase_reporting" / "PurchaseReportingReport.vue"
PURCHASE_REGISTER_PAGE = APP_ROOT / "retailedge" / "page" / "purchase_register"
SUPPLIER_PAYABLES_PAGE = APP_ROOT / "retailedge" / "page" / "supplier_payables"


class TestPurchaseReportingEdgeUI(unittest.TestCase):
	def read(self, path: Path) -> str:
		return path.read_text(encoding="utf-8")

	def test_pages_bundle_component_and_backend_exist(self):
		for path in (
			BACKEND,
			BUNDLE,
			COMPONENT,
			PURCHASE_REGISTER_PAGE / "purchase_register.js",
			PURCHASE_REGISTER_PAGE / "purchase_register.json",
			PURCHASE_REGISTER_PAGE / "purchase_register.py",
			SUPPLIER_PAYABLES_PAGE / "supplier_payables.js",
			SUPPLIER_PAYABLES_PAGE / "supplier_payables.json",
			SUPPLIER_PAYABLES_PAGE / "supplier_payables.py",
		):
			self.assertTrue(path.exists(), path)

	def test_pages_are_role_gated(self):
		for path, name in (
			(PURCHASE_REGISTER_PAGE / "purchase_register.json", "purchase-register"),
			(SUPPLIER_PAYABLES_PAGE / "supplier_payables.json", "supplier-payables"),
		):
			payload = json.loads(self.read(path))
			self.assertEqual(payload["name"], name)
			roles = {entry["role"] for entry in payload["roles"]}
			self.assertIn("Purchase User", roles)
			self.assertIn("Purchase Manager", roles)
			self.assertIn("Accounts Manager", roles)
			self.assertIn("RetailEdge Branch Manager", roles)
			self.assertIn("RetailEdge Auditor", roles)

	def test_backend_is_submitted_purchase_invoice_based_permission_aware_and_bounded(self):
		source = self.read(BACKEND)
		for contract in (
			"MAX_INVOICE_SCAN_ROWS = 2000",
			"MAX_ITEM_SCAN_ROWS = 10000",
			"MAX_PAGE_SIZE = 100",
			"MAX_LINK_RESULTS = 20",
			'"docstatus": 1',
			'frappe.get_list(\n\t\t"Purchase Invoice"',
			"limit=MAX_INVOICE_SCAN_ROWS + 1",
			'"parenttype": "Purchase Invoice"',
			"limit=MAX_ITEM_SCAN_ROWS + 1",
			"get_operational_branch_scope",
			"validate_operating_branch",
			'frappe.has_permission("Purchase Invoice", "read")',
		):
			self.assertIn(contract, source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_purchase_items_are_read_only_after_permitted_parent_names_are_known(self):
		source = inspect.getsource(purchase_reporting._build_purchase_register_dataset)
		self.assertLess(source.index("_get_permitted_invoice_headers"), source.index("_get_invoice_items"))
		item_source = inspect.getsource(purchase_reporting._get_invoice_items)
		self.assertIn('"parent": ["in", invoice_names]', item_source)

	def test_payables_ageing_boundaries_are_stable(self):
		self.assertEqual(purchase_reporting._ageing_bucket(0), "Current")
		self.assertEqual(purchase_reporting._ageing_bucket(1), "1-30 Days")
		self.assertEqual(purchase_reporting._ageing_bucket(30), "1-30 Days")
		self.assertEqual(purchase_reporting._ageing_bucket(31), "31-60 Days")
		self.assertEqual(purchase_reporting._ageing_bucket(61), "61-90 Days")
		self.assertEqual(purchase_reporting._ageing_bucket(91), "91+ Days")

	def test_frontend_uses_shared_report_shell_and_governed_export_provider(self):
		component = self.read(COMPONENT)
		bundle = self.read(BUNDLE)
		self.assertIn("EdgeReportShell", component)
		self.assertNotIn("<table", component)
		self.assertIn("createBoundedPaginatedReportProvider", bundle)
		self.assertIn("retailedge.reporting_actions.get_report_export_data", bundle)
		self.assertIn('key: "purchase-register"', bundle)
		self.assertIn('key: "supplier-payables"', bundle)
		self.assertIn("retailedge.supplier_payables.get_supplier_payables", bundle)
		for forbidden in ("new Blob", "createObjectURL", "window.print"):
			self.assertNotIn(forbidden, component)

	def test_supplier_payables_ui_does_not_claim_historical_balance_reconstruction(self):
		component = self.read(COMPONENT)
		self.assertIn("Balance Basis", component)
		self.assertIn("Current outstanding", component)
		self.assertIn("Current ERPNext outstanding balances aged at", component)
		self.assertIn("current unpaid supplier bills", component)
		self.assertNotIn(">As of Date<", component)

	def test_loaders_use_canonical_edgesuite_runtime(self):
		for path in (
			PURCHASE_REGISTER_PAGE / "purchase_register.js",
			SUPPLIER_PAYABLES_PAGE / "supplier_payables.js",
		):
			loader = self.read(path)
			self.assertIn('const EDGEUI_ASSET = "edgeui.bundle.js"', loader)
			self.assertIn('const PURCHASE_REPORTING_ASSET = "purchase_reporting.bundle.js"', loader)
			self.assertIn("window.mountPurchaseReportingPage", loader)
			self.assertIn("hideNativePageSidebar", loader)


if __name__ == "__main__":
	unittest.main()
