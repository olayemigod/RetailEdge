from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from retailedge.cash_custody import (
	CASH_DEPOSIT_TYPE,
	get_cash_custody_snapshot,
	validate_cash_deposit_before_submit,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestCashCustody(unittest.TestCase):
	@patch("retailedge.cash_custody.get_submitted_cash_deposits")
	@patch("retailedge.cash_custody.get_shift_cash_snapshot")
	def test_snapshot_subtracts_only_submitted_deposits(self, mock_shift_snapshot, mock_deposits):
		mock_shift_snapshot.return_value = {
			"opening_cash": 10000,
			"cash_sales": 50000,
			"prior_expenses": 5000,
			"available_before": 55000,
			"source": "shift",
			"message": None,
		}
		mock_deposits.return_value = [
			{"paid_amount": 12000},
			{"paid_amount": 8000},
		]

		result = get_cash_custody_snapshot(
			opening_shift="SHIFT-0001",
			company="Demo Company",
			cashier="cashier@example.com",
		)

		self.assertEqual(result["opening_cash"], 10000)
		self.assertEqual(result["cash_sales"], 50000)
		self.assertEqual(result["cashier_expenses"], 5000)
		self.assertEqual(result["submitted_deposits"], 20000)
		self.assertEqual(result["available_cash"], 35000)
		self.assertEqual(result["submitted_deposit_count"], 2)


	@patch("retailedge.cash_custody.get_submitted_cash_deposits", return_value=[{"paid_amount": 2000}])
	@patch("retailedge.cash_custody.get_shift_cash_snapshot")
	def test_editing_expense_excludes_self_but_never_submitted_deposits(self, snapshot, deposits):
		snapshot.return_value = {
			"opening_cash": 10000, "cash_sales": 3000, "prior_expenses": 1000,
			"available_before": 12000, "source": "shift", "message": None,
		}
		position = get_cash_custody_snapshot(
			opening_shift="POSA-OS-26-0000009", company="Retail Co",
			pos_profile="POS-1", cashier="cashier@example.com",
			expense_name="EXP-1",
		)
		self.assertEqual(position["available_cash"], 10000)
		snapshot.assert_called_once_with(
			opening_shift="POSA-OS-26-0000009", company="Retail Co",
			pos_profile="POS-1", user="cashier@example.com", expense_name="EXP-1",
			for_cash_validation=False,
		)

	@patch("retailedge.cash_custody.get_submitted_cash_deposits", return_value=[{"paid_amount": 2000}])
	@patch("retailedge.cash_custody.get_shift_cash_snapshot")
	def test_spend_gate_uses_current_locked_read_for_expenses_and_deposits(self, snapshot, deposits):
		snapshot.return_value = {
			"opening_cash": 10000, "cash_sales": 0, "prior_expenses": 1000,
			"available_before": 9000, "cash_sales_verified": True,
		}
		position = get_cash_custody_snapshot(
			opening_shift="OPEN-1", company="Retail Co", cashier="cashier@example.com",
			for_spending_validation=True,
		)
		self.assertEqual(position["available_cash"], 7000)
		self.assertTrue(position["cash_sales_verified"])
		self.assertTrue(snapshot.call_args.kwargs["for_cash_validation"])
		self.assertTrue(deposits.call_args.kwargs["for_cash_validation"])

	def test_expense_document_uses_submitted_deposit_aware_custody(self):
		controller = (APP_ROOT / "retailedge" / "doctype" / "retailedge_cashier_expense" / "retailedge_cashier_expense.py").read_text(encoding="utf-8")
		context = (APP_ROOT / "cashier_context.py").read_text(encoding="utf-8")
		self.assertIn("get_cash_custody_snapshot(", controller)
		self.assertIn('snapshot.get("available_cash", 0)', controller)
		self.assertIn("get_cash_custody_snapshot(", context)
		self.assertIn('snapshot.get("available_cash", 0.0)', context)

	def test_non_deposit_payment_entry_is_not_custody_gated(self):
		doc = SimpleNamespace(
			doctype="Payment Entry",
			retailedge_cash_custody_type="",
			payment_type="Receive",
		)
		with patch("retailedge.cash_custody.frappe.db.sql") as mock_sql:
			validate_cash_deposit_before_submit(doc)
		mock_sql.assert_not_called()

	def test_custody_contract_preserves_erpnext_accounting_truth(self):
		source = (APP_ROOT / "cash_custody.py").read_text(encoding="utf-8")
		hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
		self.assertEqual(CASH_DEPOSIT_TYPE, "Cash Deposit")
		self.assertIn('doc.payment_type = "Internal Transfer"', source)
		self.assertIn('expected_type="Cash"', source)
		self.assertIn('expected_type="Bank"', source)
		self.assertIn('"docstatus": 1', source)
		self.assertIn("doc.insert()", source)
		self.assertNotIn("doc.submit()", source)
		self.assertNotIn("frappe.db.commit()", source)
		self.assertIn("FOR UPDATE", source)
		self.assertIn('"before_submit": "retailedge.cash_custody.validate_cash_deposit_before_submit"', hooks)
		self.assertIn('"retailedge.cash_custody.ensure_cash_custody_custom_fields"', hooks)

	def test_custom_fields_are_durable_and_hidden_from_normal_payment_entry_ui(self):
		source = (APP_ROOT / "cash_custody.py").read_text(encoding="utf-8")
		for fieldname in (
			"retailedge_cash_custody_type",
			"retailedge_cashier",
			"retailedge_pos_opening_shift",
		):
			self.assertIn(fieldname, source)
		self.assertIn("create_custom_fields", source)
		self.assertIn('"read_only": 1', source)
		self.assertIn('"hidden": 1', source)


if __name__ == "__main__":
	unittest.main()
