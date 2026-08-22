from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.supplier_obligations_control import _build_supplier_control

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeSupplierObligationsControlTests(unittest.TestCase):
	def test_supplier_exposure_and_priorities_are_deterministic(self):
		payables = {"balance_basis": "current_outstanding", "ageing_date": "2026-08-22", "scan": {"invoice_limit": 2000}}
		rows = [
			{"invoice": "PINV-1", "supplier": "SUP-A", "supplier_name": "Supplier A", "outstanding": 1000, "overdue_days": 100, "ageing_bucket": "91+ Days", "due_date": "2026-05-14"},
			{"invoice": "PINV-2", "supplier": "SUP-B", "supplier_name": "Supplier B", "outstanding": 3000, "overdue_days": 45, "ageing_bucket": "31-60 Days", "due_date": "2026-07-08"},
			{"invoice": "PINV-3", "supplier": "SUP-A", "supplier_name": "Supplier A", "outstanding": 2000, "overdue_days": 0, "ageing_bucket": "Current", "due_date": "2026-09-01"},
		]
		result = _build_supplier_control(payables, rows)
		self.assertEqual(result["supplier_exposure"][0]["supplier"], "SUP-A")
		self.assertEqual(result["supplier_exposure"][0]["outstanding"], 3000)
		self.assertEqual(result["payment_priorities"][0]["invoice"], "PINV-1")
		self.assertEqual(result["payment_priorities"][0]["priority"], "Critical")
		self.assertTrue(result["payment_priorities"][0]["open_in_new_tab"])
		self.assertEqual(result["oldest_overdue"][0]["invoice"], "PINV-1")

	def test_control_service_reuses_payables_engine_and_does_not_query_business_tables(self):
		source = (APP_ROOT / "supplier_obligations_control.py").read_text()
		self.assertIn("get_supplier_payables_export", source)
		self.assertNotIn('frappe.get_list("Purchase Invoice"', source)
		self.assertNotIn('frappe.db.get_all("Purchase Invoice"', source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertIn("historical_balance_supported", source)
		self.assertIn("open_in_new_tab", source)


if __name__ == "__main__":
	unittest.main()
