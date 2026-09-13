from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.customer_receivables import MAX_INVOICE_SCAN_ROWS, _ageing_bucket

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeCustomerReceivablesTests(unittest.TestCase):
	def test_ageing_buckets_are_stable(self):
		self.assertEqual(_ageing_bucket(0), "Current")
		self.assertEqual(_ageing_bucket(1), "1-30 Days")
		self.assertEqual(_ageing_bucket(30), "1-30 Days")
		self.assertEqual(_ageing_bucket(31), "31-60 Days")
		self.assertEqual(_ageing_bucket(60), "31-60 Days")
		self.assertEqual(_ageing_bucket(61), "61-90 Days")
		self.assertEqual(_ageing_bucket(90), "61-90 Days")
		self.assertEqual(_ageing_bucket(91), "91+ Days")

	def test_backend_uses_submitted_sales_invoice_truth_and_bounded_scan(self):
		source = (APP_ROOT / "customer_receivables.py").read_text()
		self.assertIn('"docstatus": 1', source)
		self.assertIn('"is_return": 0', source)
		self.assertIn('"company": filters.company', source)
		self.assertIn('"outstanding_amount"', source)
		self.assertIn("limit=MAX_INVOICE_SCAN_ROWS + 1", source)
		self.assertEqual(MAX_INVOICE_SCAN_ROWS, 2000)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)

	def test_current_outstanding_is_not_presented_as_historical_reconstruction(self):
		source = (APP_ROOT / "customer_receivables.py").read_text()
		component = (
			APP_ROOT / "public" / "js" / "customer_receivables" / "CustomerReceivablesReport.vue"
		).read_text()
		self.assertIn("current ERPNext outstanding balances only", source)
		self.assertIn("Historical balances require ledger reconstruction", source)
		self.assertIn("Balance Basis", component)
		self.assertIn("Current outstanding", component)
		self.assertNotIn(">As of Date<", component)

	def test_branch_scope_is_server_authoritative(self):
		source = (APP_ROOT / "customer_receivables.py").read_text()
		self.assertIn("get_operational_branch_scope", source)
		self.assertIn("validate_operating_branch", source)
		self.assertNotIn("validate_user_branch_access", source)
		self.assertNotIn("get_user_allowed_branches", source)
		self.assertNotIn("user_has_global_branch_access", source)
		self.assertIn("branch-restricted receivables cannot be applied safely", source)


if __name__ == "__main__":
	unittest.main()
