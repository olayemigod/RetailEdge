from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PAGE = APP_ROOT / "retailedge" / "page" / "customer_receivables"
BUNDLE = APP_ROOT / "public" / "js" / "customer_receivables.bundle.js"
COMPONENT = APP_ROOT / "public" / "js" / "customer_receivables" / "CustomerReceivablesReport.vue"


class RetailEdgeCustomerReceivablesEdgeUITests(unittest.TestCase):
	def test_standard_page_exists_with_expected_roles(self):
		data = json.loads((PAGE / "customer_receivables.json").read_text())
		self.assertEqual(data["name"], "customer-receivables")
		self.assertEqual(data["standard"], "Yes")
		roles = {row["role"] for row in data["roles"]}
		self.assertIn("Sales Manager", roles)
		self.assertIn("Accounts Manager", roles)
		self.assertIn("RetailEdge Manager", roles)

	def test_component_uses_shared_report_shell(self):
		source = COMPONENT.read_text()
		self.assertIn("<EdgeReportShell", source)
		self.assertIn("<EdgeLinkField", source)
		self.assertNotIn("<table", source)
		self.assertIn("Current ERPNext outstanding balances aged at", source)
		self.assertIn('frappe.set_route("Form", "Sales Invoice", value)', source)
		self.assertIn('frappe.set_route("Form", "Customer", value)', source)

	def test_provider_is_bounded_and_governed(self):
		source = BUNDLE.read_text()
		self.assertIn("createBoundedPaginatedReportProvider", source)
		self.assertIn('key: REPORT_KEY', source)
		self.assertIn('const REPORT_KEY = "customer-receivables"', source)
		self.assertIn("maxDatasetRows: 2000", source)
		self.assertIn("retailedge.reporting_actions.get_report_export_data", source)

	def test_loader_uses_canonical_edgesuite_runtime(self):
		source = (PAGE / "customer_receivables.js").read_text()
		self.assertIn('const EDGEUI_ASSET = "edgeui.bundle.js"', source)
		self.assertIn('const RECEIVABLES_ASSET = "customer_receivables.bundle.js"', source)
		self.assertIn("window.EdgeSuiteUI", source)
		self.assertNotIn("window.EdgeUI", source)

	def test_reporting_governance_knows_customer_receivables(self):
		actions = (APP_ROOT / "public" / "js" / "retailedge_reporting_actions.js").read_text()
		capabilities = (APP_ROOT / "reporting_capabilities.py").read_text()
		dispatch = (APP_ROOT / "reporting_actions.py").read_text()
		self.assertIn('"/app/customer-receivables": "customer-receivables"', actions)
		self.assertIn('"customer-receivables": ReportCapabilitySpec', capabilities)
		self.assertIn('if key == "customer-receivables"', dispatch)


if __name__ == "__main__":
	unittest.main()
