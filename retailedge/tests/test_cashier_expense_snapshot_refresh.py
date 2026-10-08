from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from retailedge.cashier_expense_snapshot import refresh_cashier_expense_cash_snapshot


class TestCashierExpenseSnapshotRefresh(unittest.TestCase):
	@patch("retailedge.cashier_expense_snapshot.frappe.db.set_value")
	@patch("retailedge.cashier_expense_snapshot.get_shift_cash_snapshot")
	@patch("retailedge.cashier_expense_snapshot.frappe.get_doc")
	@patch("retailedge.cashier_expense_snapshot.frappe.session", SimpleNamespace(user="Administrator"))
	def test_refresh_clears_stale_warning_without_touching_accounting_fields(
		self,
		mock_get_doc,
		mock_snapshot,
		mock_set_value,
	):
		mock_get_doc.return_value = SimpleNamespace(
			doctype="RetailEdge Cashier Expense",
			name="RE-CE-2026-0017",
			docstatus=1,
			company="RetailEdge Consulting",
			pos_profile="Ketu POS Profile",
			cashier="Administrator",
			linked_pos_opening_shift="POSA-OS-26-0000006",
			amount=1500,
			expense_status="Posted",
			ledger_status="Posted",
			posting_reference="ACC-JV-2026-00010",
		)
		mock_snapshot.return_value = {
			"opening_cash": 100000,
			"cash_sales": 0,
			"prior_expenses": 2000,
			"available_before": 98000,
			"source": "opening_shift.balance_details + sales_invoice.posa_pos_opening_shift + retailedge_expenses",
			"message": None,
		}

		result = refresh_cashier_expense_cash_snapshot("RE-CE-2026-0017")

		values = mock_set_value.call_args.args[2]
		self.assertEqual(values["shift_opening_cash_amount"], 100000)
		self.assertEqual(values["shift_cash_sales_amount"], 0)
		self.assertEqual(values["prior_shift_expense_amount"], 2000)
		self.assertEqual(values["available_shift_cash_before_expense"], 98000)
		self.assertEqual(values["available_shift_cash_after_expense"], 96500)
		self.assertIsNone(values["cash_control_message"])
		self.assertNotIn("expense_status", values)
		self.assertNotIn("ledger_status", values)
		self.assertNotIn("posting_reference", values)
		self.assertEqual(result["expense_name"], "RE-CE-2026-0017")

	def test_refresh_requires_expense_name(self):
		with self.assertRaises(Exception):
			refresh_cashier_expense_cash_snapshot("")


if __name__ == "__main__":
	unittest.main()
