from __future__ import annotations

import unittest
from pathlib import Path

from frappe.utils import getdate

from retailedge.receivables_control import _build_receivables_control

APP_ROOT = Path(__file__).resolve().parents[1]


class TestReceivablesControl(unittest.TestCase):
	def test_builds_exposure_concentration_and_collection_priorities(self):
		dataset = {
			"rows": [
				{
					"customer": "CUST-A",
					"customer_name": "Alpha",
					"invoice": "SINV-1",
					"due_date": "2026-04-01",
					"posting_date": "2026-03-01",
					"outstanding": 6000,
					"overdue_days": 120,
					"ageing_bucket": "91+ Days",
				},
				{
					"customer": "CUST-A",
					"customer_name": "Alpha",
					"invoice": "SINV-2",
					"due_date": "2026-08-05",
					"posting_date": "2026-07-10",
					"outstanding": 2000,
					"overdue_days": 17,
					"ageing_bucket": "1-30 Days",
				},
				{
					"customer": "CUST-B",
					"customer_name": "Beta",
					"invoice": "SINV-3",
					"due_date": "2026-07-01",
					"posting_date": "2026-06-01",
					"outstanding": 2000,
					"overdue_days": 52,
					"ageing_bucket": "31-60 Days",
				},
			],
			"balance_basis": "current_outstanding",
			"current_balance_date": "2026-08-22",
			"scan": {"invoices": 3, "invoice_limit": 2000},
		}
		result = _build_receivables_control(
			dataset,
			company="Demo",
			branch="",
			from_date=getdate("2026-08-01"),
			to_date=getdate("2026-08-22"),
		)

		self.assertEqual(result["summary"][0]["value"], 10000)
		self.assertEqual(result["top_customer_exposures"][0]["customer"], "CUST-A")
		self.assertAlmostEqual(result["top_customer_exposures"][0]["share_percent"], 80.0)
		self.assertEqual(result["collection_priorities"][0]["invoice"], "SINV-1")
		self.assertEqual(result["collection_priorities"][0]["priority"], "Critical")
		self.assertEqual([row["invoice"] for row in result["newly_overdue"]], ["SINV-2"])

	def test_newly_overdue_is_explicitly_current_outstanding_not_historical_reconstruction(self):
		result = _build_receivables_control(
			{
				"rows": [],
				"balance_basis": "current_outstanding",
				"current_balance_date": "2026-08-22",
			},
			company="Demo",
			branch="Aba",
			from_date=getdate("2026-08-01"),
			to_date=getdate("2026-08-22"),
		)
		self.assertIn("currently outstanding invoices", result["metadata"]["newly_overdue_definition"])
		self.assertIn("not a historical receivables reconstruction", result["metadata"]["newly_overdue_definition"])
		self.assertEqual(result["metadata"]["balance_basis"], "current_outstanding")

	def test_source_contract_reuses_customer_receivables_and_avoids_parallel_ledger(self):
		source = (APP_ROOT / "receivables_control.py").read_text(encoding="utf-8")
		self.assertIn("get_customer_receivables_export", source)
		self.assertIn("require_dashboard_action", source)
		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn("frappe.get_list", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)

	def test_native_invoice_contract_is_new_tab_safe_for_ui_consumers(self):
		result = _build_receivables_control(
			{"rows": []},
			company="Demo",
			branch="",
			from_date=getdate("2026-08-01"),
			to_date=getdate("2026-08-22"),
		)
		self.assertEqual(result["metadata"]["native_invoice_route"], "/app/sales-invoice/{name}")
		self.assertTrue(result["metadata"]["native_links_open_new_tab"])


if __name__ == "__main__":
	unittest.main()
