from __future__ import annotations

import unittest
from pathlib import Path

from frappe.utils import add_days, getdate

from retailedge.cash_flow_outlook import OUTLOOK_WEEKS, _bucket_index, _empty_buckets

APP_ROOT = Path(__file__).resolve().parents[1]


class TestCashFlowOutlookContract(unittest.TestCase):
	def test_due_now_and_thirteen_week_bucket_boundaries(self):
		anchor = getdate("2026-08-29")
		self.assertEqual(OUTLOOK_WEEKS, 13)
		self.assertEqual(_bucket_index(anchor, anchor), 0)
		self.assertEqual(_bucket_index(add_days(anchor, 1), anchor), 1)
		self.assertEqual(_bucket_index(add_days(anchor, 7), anchor), 1)
		self.assertEqual(_bucket_index(add_days(anchor, 8), anchor), 2)
		self.assertEqual(_bucket_index(add_days(anchor, 91), anchor), 13)
		self.assertIsNone(_bucket_index(add_days(anchor, 92), anchor))
		self.assertEqual(len(_empty_buckets(anchor)), 14)

	def test_backend_reuses_erpnext_receivable_payable_allocation_and_branch_scopes(self):
		source = (APP_ROOT / "cash_flow_outlook.py").read_text()
		self.assertIn("ReceivablePayableReport", source)
		self.assertIn('"based_on_payment_terms": 1', source)
		self.assertIn("customer_receivables._get_permitted_invoice_headers", source)
		self.assertIn("purchase_reporting._get_permitted_invoice_headers", source)
		self.assertIn('voucher_type="Sales Invoice"', source)
		self.assertIn('voucher_type="Purchase Invoice"', source)
		self.assertIn("get_operational_branch_scope", source)
		self.assertIn("validate_operating_branch", source)
		self.assertNotIn("validate_user_branch_access", source)
		self.assertNotIn("get_user_allowed_branches", source)
		self.assertNotIn("user_has_global_branch_access", source)
		self.assertIn('"forecasting": False', source)
		self.assertIn('"cash_balance_included": False', source)
		self.assertIn('"journal_entries_included": False', source)
		self.assertIn('"orders_included": False', source)
		self.assertIn('"manual_scenarios_included": False', source)
		self.assertNotIn("build_baseline_forecast", source)
		self.assertNotIn("from retailedge.forecasting", source)

	def test_outlook_is_read_only_and_never_posts_accounting(self):
		source = (APP_ROOT / "cash_flow_outlook.py").read_text()
		for forbidden in (
			"frappe.new_doc(",
			".insert(",
			".submit(",
			"frappe.db.set_value(",
			'frappe.get_doc("GL Entry"',
			'frappe.get_doc("Stock Ledger Entry"',
		):
			self.assertNotIn(forbidden, source)

	def test_edgesuite_page_is_explicitly_commitments_not_forecasting(self):
		bundle = (APP_ROOT / "public" / "js" / "cash_flow_outlook.bundle.js").read_text()
		component = (
			APP_ROOT / "public" / "js" / "cash_flow_outlook" / "CashFlowOutlookReport.vue"
		).read_text()
		page = (APP_ROOT / "retailedge" / "page" / "cash_flow_outlook" / "cash_flow_outlook.js").read_text()
		self.assertIn("window.EdgeSuiteUI", bundle)
		self.assertIn("window.EdgeSuiteUI", component)
		self.assertIn("window.EdgeSuiteUI", page)
		self.assertNotIn("window.EdgeUI", bundle)
		self.assertNotIn("window.EdgeUI", component)
		self.assertNotIn("window.EdgeUI", page)
		self.assertIn("EdgeReportShell", component)
		self.assertIn("13-Week Cash Commitments", component)
		self.assertIn("Forecasting remains in Forecasting & Planning", component)
		self.assertIn("known-commitments schedule", component)

	def test_shared_navigation_export_and_capability_registries_include_outlook(self):
		navigation = (APP_ROOT / "edgesuite_ui.py").read_text()
		actions = (APP_ROOT / "reporting_actions.py").read_text()
		capabilities = (APP_ROOT / "reporting_capabilities.py").read_text()
		self.assertIn('"Cash Flow Outlook"', navigation)
		self.assertIn('"target": "cash-flow-outlook"', navigation)
		self.assertIn('key == "cash-flow-outlook"', actions)
		self.assertIn('"cash-flow-outlook": ReportCapabilitySpec(', capabilities)


if __name__ == "__main__":
	unittest.main()
