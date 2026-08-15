from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.guided_cashier_expense import (
	MAX_LINK_RESULTS,
	create_guided_cashier_expense_draft,
	get_guided_cashier_expense_context,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _DraftCashierExpense(SimpleNamespace):
	doctype = "RetailEdge Cashier Expense"

	def __init__(self):
		super().__init__(
			name="RE-CE-GUIDED-0001",
			docstatus=0,
			expense_status="Draft",
			company=None,
			branch=None,
			cashier=None,
			expense_category=None,
			amount=0,
			available_shift_cash_after_expense=0,
			insert_calls=0,
		)

	def insert(self):
		self.insert_calls += 1
		self.company = "Demo Company"
		self.branch = "Lagos"
		self.cashier = "cashier@example.com"
		self.available_shift_cash_after_expense = 750
		return self


class TestGuidedCashierExpense(unittest.TestCase):
	@patch("retailedge.guided_cashier_expense._assert_can_create_expense")
	@patch("retailedge.guided_cashier_expense.get_cashier_expense_entry_context")
	def test_context_surfaces_shift_cash_and_readiness(self, mock_context, _mock_permission):
		mock_context.return_value = {
			"user": "cashier@example.com",
			"cashier": "cashier@example.com",
			"company": "Demo Company",
			"branch": "Lagos",
			"pos_profile": "POS-LAGOS",
			"linked_pos_opening_shift": "POS-OPEN-1",
			"payment_account": "Cash - DC",
			"cost_center": "Lagos - DC",
			"shift_opening_cash_amount": 1000,
			"shift_cash_sales_amount": 500,
			"prior_shift_expense_amount": 250,
			"available_shift_cash_before_expense": 1250,
			"cash_control_message": "Cash is available.",
			"settings": {
				"require_open_shift_for_cashier_expense": True,
				"allow_cashier_expense_without_cash_account": False,
				"allow_cashier_expense_date_edit": False,
			},
		}
		result = get_guided_cashier_expense_context()
		self.assertTrue(result["ready"])
		self.assertEqual(result["blocking_reasons"], [])
		self.assertEqual(result["context"]["opening_shift"], "POS-OPEN-1")
		self.assertEqual(result["context"]["available_cash"], 1250.0)
		self.assertFalse(result["capabilities"]["allow_expense_date_edit"])

	@patch("retailedge.guided_cashier_expense._assert_can_create_expense")
	@patch("retailedge.guided_cashier_expense.get_cashier_expense_entry_context")
	def test_context_blocks_known_missing_shift_and_cash_account(self, mock_context, _mock_permission):
		mock_context.return_value = {
			"company": "Demo Company",
			"settings": {
				"require_open_shift_for_cashier_expense": True,
				"allow_cashier_expense_without_cash_account": False,
			},
		}
		result = get_guided_cashier_expense_context()
		self.assertFalse(result["ready"])
		self.assertEqual(len(result["blocking_reasons"]), 2)

	@patch("retailedge.guided_cashier_expense._assert_active_category")
	@patch("retailedge.guided_cashier_expense._assert_can_create_expense")
	@patch("retailedge.guided_cashier_expense.frappe.new_doc")
	def test_create_draft_sets_only_business_inputs_then_relies_on_controller(
		self, mock_new_doc, _mock_permission, mock_category
	):
		doc = _DraftCashierExpense()
		mock_new_doc.return_value = doc
		result = create_guided_cashier_expense_draft(
			{
				"expense_category": "Transport",
				"amount": 500,
				"description": "Delivery bike fuel",
				"expense_date": "2026-08-15",
				"company": "Spoof Company",
				"branch": "Spoof Branch",
				"payment_account": "Spoof Account",
				"expense_account": "Spoof Expense",
				"cost_center": "Spoof CC",
			}
		)
		mock_new_doc.assert_called_once_with("RetailEdge Cashier Expense")
		mock_category.assert_called_once_with("Transport")
		self.assertEqual(doc.insert_calls, 1)
		self.assertEqual(doc.expense_category, "Transport")
		self.assertEqual(doc.amount, 500.0)
		self.assertEqual(doc.description, "Delivery bike fuel")
		self.assertEqual(str(doc.expense_date), "2026-08-15")
		self.assertEqual(doc.company, "Demo Company")
		self.assertEqual(doc.branch, "Lagos")
		self.assertFalse(hasattr(doc, "payment_account"))
		self.assertFalse(hasattr(doc, "expense_account"))
		self.assertFalse(hasattr(doc, "cost_center"))
		self.assertEqual(result["available_cash_after"], 750.0)

	def test_adapter_is_bounded_permission_aware_and_draft_only(self):
		source = (APP_ROOT / "guided_cashier_expense.py").read_text()
		self.assertIn("MAX_LINK_RESULTS = 20", source)
		self.assertIn("limit_page_length=limit", source)
		self.assertIn("frappe.get_list(", source)
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn("doc.insert()", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("doc.submit()", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_adapter_does_not_assign_accounting_or_shift_context_fields(self):
		source = (APP_ROOT / "guided_cashier_expense.py").read_text()
		for forbidden in (
			"doc.company =",
			"doc.branch =",
			"doc.cashier =",
			"doc.pos_profile =",
			"doc.linked_pos_opening_shift =",
			"doc.payment_account =",
			"doc.cost_center =",
			"doc.expense_account =",
		):
			self.assertNotIn(forbidden, source)
		self.assertIn("controller resolves cashier/company/", source)

	def test_dialog_uses_shared_edgesuite_components_and_live_cash_preview(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimpleCashierExpenseDialog.vue"
		).read_text()
		self.assertIn("EdgeModal: runtimeComponents.EdgeModal", component)
		self.assertIn("EdgeLinkField: runtimeComponents.EdgeLinkField", component)
		self.assertIn("available_cash", component)
		self.assertIn("projectedCash", component)
		self.assertIn("blockingReasons", component)
		self.assertIn("projectedCash < 0", component)
		self.assertIn("Expense Category", component)
		self.assertIn("Open Full Form", component)
		self.assertIn('this.$emit("open-native", "RetailEdge Cashier Expense")', component)
		self.assertNotIn("expense_account", component)
		self.assertNotIn("cost_center", component)

	def test_limit_is_small_for_category_search(self):
		self.assertEqual(MAX_LINK_RESULTS, 20)


if __name__ == "__main__":
	unittest.main()
