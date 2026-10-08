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
	def test_submitted_refresh_clears_warning_but_preserves_historical_money(
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
			shift_opening_cash_amount=100000,
			shift_cash_sales_amount=0,
			prior_shift_expense_amount=2000,
			available_shift_cash_before_expense=98000,
			available_shift_cash_after_expense=96500,
			expense_status="Posted",
			ledger_status="Posted",
			posting_reference="ACC-JV-2026-00010",
		)
		# Current shift context has moved on after later expenses. Those values must
		# not rewrite the submitted record's original point-in-time snapshot.
		mock_snapshot.return_value = {
			"opening_cash": 100000,
			"cash_sales": 0,
			"prior_expenses": 4500,
			"available_before": 95500,
			"source": "opening_shift.balance_details + sales_invoice.posa_pos_opening_shift + retailedge_expenses",
			"message": None,
		}

		result = refresh_cashier_expense_cash_snapshot("RE-CE-2026-0017")

		values = mock_set_value.call_args.args[2]
		self.assertEqual(
			values,
			{
				"cash_balance_source": "opening_shift.balance_details + sales_invoice.posa_pos_opening_shift + retailedge_expenses",
				"cash_control_message": None,
			},
		)
		self.assertTrue(result["monetary_snapshot_preserved"])
		self.assertEqual(result["shift_opening_cash_amount"], 100000)
		self.assertEqual(result["shift_cash_sales_amount"], 0)
		self.assertEqual(result["prior_shift_expense_amount"], 2000)
		self.assertEqual(result["available_shift_cash_before_expense"], 98000)
		self.assertEqual(result["available_shift_cash_after_expense"], 96500)
		self.assertNotIn("expense_status", values)
		self.assertNotIn("ledger_status", values)
		self.assertNotIn("posting_reference", values)

	@patch("retailedge.cashier_expense_snapshot.frappe.db.set_value")
	@patch("retailedge.cashier_expense_snapshot.get_shift_cash_snapshot")
	@patch("retailedge.cashier_expense_snapshot.frappe.get_doc")
	@patch("retailedge.cashier_expense_snapshot.frappe.session", SimpleNamespace(user="Administrator"))
	def test_draft_refresh_recomputes_full_snapshot(self, mock_get_doc, mock_snapshot, mock_set_value):
		mock_get_doc.return_value = SimpleNamespace(
			doctype="RetailEdge Cashier Expense",
			name="RE-CE-DRAFT-1",
			docstatus=0,
			company="RetailEdge Consulting",
			pos_profile="Ketu POS Profile",
			cashier="Administrator",
			linked_pos_opening_shift="POSA-OS-26-0000006",
			amount=1500,
		)
		mock_snapshot.return_value = {
			"opening_cash": 100000,
			"cash_sales": 5000,
			"prior_expenses": 4500,
			"available_before": 100500,
			"source": "resolved source",
			"message": None,
		}

		result = refresh_cashier_expense_cash_snapshot("RE-CE-DRAFT-1")

		values = mock_set_value.call_args.args[2]
		self.assertFalse(result["monetary_snapshot_preserved"])
		self.assertEqual(values["shift_opening_cash_amount"], 100000)
		self.assertEqual(values["shift_cash_sales_amount"], 5000)
		self.assertEqual(values["prior_shift_expense_amount"], 4500)
		self.assertEqual(values["available_shift_cash_before_expense"], 100500)
		self.assertEqual(values["available_shift_cash_after_expense"], 99000)
		self.assertIsNone(values["cash_control_message"])

	@patch("retailedge.cashier_expense_snapshot.frappe.db.set_value")
	@patch("retailedge.cashier_expense_snapshot.get_shift_cash_snapshot")
	@patch("retailedge.cashier_expense_snapshot.frappe.get_doc")
	@patch("retailedge.cashier_expense_snapshot.frappe.session", SimpleNamespace(user="Administrator"))
	def test_submitted_refresh_preserves_money_and_writes_unresolved_warning(
		self,
		mock_get_doc,
		mock_snapshot,
		mock_set_value,
	):
		mock_get_doc.return_value = SimpleNamespace(
			doctype="RetailEdge Cashier Expense",
			name="RE-CE-SUBMITTED-1",
			docstatus=1,
			company="RetailEdge Consulting",
			pos_profile="Ketu POS Profile",
			cashier="Administrator",
			linked_pos_opening_shift="POSA-OS-TEST",
			amount=500,
			shift_opening_cash_amount=10000,
			shift_cash_sales_amount=2000,
			prior_shift_expense_amount=1000,
			available_shift_cash_before_expense=11000,
			available_shift_cash_after_expense=10500,
		)
		mock_snapshot.return_value = {
			"opening_cash": 0,
			"cash_sales": 0,
			"prior_expenses": 0,
			"available_before": 0,
			"source": "unresolved",
			"message": "Cash sales could not be safely resolved for this POS schema.",
		}

		result = refresh_cashier_expense_cash_snapshot("RE-CE-SUBMITTED-1")

		values = mock_set_value.call_args.args[2]
		self.assertEqual(values["cash_balance_source"], "unresolved")
		self.assertIn("could not be safely resolved", values["cash_control_message"])
		self.assertTrue(result["monetary_snapshot_preserved"])
		self.assertEqual(result["available_shift_cash_after_expense"], 10500)

	def test_refresh_requires_expense_name(self):
		with self.assertRaises(Exception):
			refresh_cashier_expense_cash_snapshot("")


if __name__ == "__main__":
	unittest.main()
