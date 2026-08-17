from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
COMPONENT = APP_ROOT / "public" / "js" / "cash_movement" / "CashMovementReport.vue"


class TestCashMovementUI(unittest.TestCase):
	def test_page_is_role_restricted_and_excludes_cashier_only_roles(self):
		path = APP_ROOT / "retailedge" / "page" / "cash_movement" / "cash_movement.json"
		data = json.loads(path.read_text())
		roles = {row["role"] for row in data["roles"]}
		self.assertIn("RetailEdge Branch Manager", roles)
		self.assertIn("RetailEdge Auditor", roles)
		self.assertIn("Accounts Manager", roles)
		self.assertNotIn("RetailEdge Cashier", roles)
		self.assertNotIn("RetailEdgeCashier", roles)

	def test_page_mounts_only_one_edgesuite_shell(self):
		page = (
			APP_ROOT / "retailedge" / "page" / "cash_movement" / "cash_movement.js"
		).read_text()
		bundle = (APP_ROOT / "public" / "js" / "cash_movement.bundle.js").read_text()
		self.assertIn('const EDGEUI_ASSET = "edgeui.bundle.js"', page)
		self.assertIn('const CASH_MOVEMENT_ASSET = "cash_movement.bundle.js"', page)
		self.assertIn("hideNativePageSidebar", page)
		self.assertIn("window.mountCashMovement", page)
		self.assertIn('import CashMovement from "./cash_movement/CashMovementReport.vue"', bundle)

	def test_frontend_uses_shared_report_shell_provider_and_server_search(self):
		component = COMPONENT.read_text()
		self.assertIn("EdgeAppShell", component)
		self.assertIn("EdgeReportShell", component)
		self.assertIn("EdgeLinkField", component)
		self.assertIn("EdgeExportMenu", component)
		self.assertIn("search_cash_movement_options", component)
		self.assertIn(':pageSizes="[25, 50, 100]"', component)
		self.assertIn("Posted accounting entries only", component)
		self.assertIn("this.reportProvider.load", component)
		self.assertIn("this.filters.branch = \"\"", component)
		self.assertIn("this.filters.account = \"\"", component)
		self.assertNotIn("<table", component)
		self.assertNotIn("localStorage", component)
		self.assertNotIn("sessionStorage", component)

	def test_cash_movement_registers_edgesuite_paginated_provider(self):
		bundle = (APP_ROOT / "public" / "js" / "cash_movement.bundle.js").read_text()
		self.assertIn('const REPORT_PRODUCT = "RetailEdge"', bundle)
		self.assertIn('const REPORT_KEY = "cash-movement"', bundle)
		self.assertIn("createPaginatedReportProvider", bundle)
		self.assertIn("registerProvider(REPORT_PRODUCT, REPORT_KEY", bundle)
		self.assertIn("defaultPageLength: 50", bundle)
		self.assertIn("maxPageLength: 100", bundle)
		self.assertIn("Math.floor", bundle)
		self.assertIn("get_cash_movement", bundle)
		self.assertIn("get_cash_movement_export", bundle)
		self.assertNotIn("for (let page", bundle)
		self.assertNotIn("setInterval(", bundle)

	def test_frontend_preserves_accounting_scope_and_drilldown(self):
		component = COMPONENT.read_text()
		self.assertNotIn("Party Name", component)
		self.assertNotIn("Cashier", component)
		self.assertNotIn("Employee", component)
		self.assertIn("Cash / Bank Account", component)
		self.assertIn("Movement Type", component)
		self.assertIn("Posted ERPNext General Ledger Cash/Bank entries", component)
		self.assertIn('column.fieldname === "voucher_no"', component)
		self.assertIn('frappe.set_route("Form", row.voucher_type, row.voucher_no)', component)


if __name__ == "__main__":
	unittest.main()
