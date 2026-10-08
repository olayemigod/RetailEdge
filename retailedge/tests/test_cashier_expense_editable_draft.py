from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.guided_cashier_expense import update_guided_cashier_expense_draft

APP_ROOT = Path(__file__).resolve().parents[1]
SIMPLE_DIALOG = APP_ROOT / "public/js/retailedge_business_hub/SimpleCashierExpenseDialog.vue"


class _EditableDraft(SimpleNamespace):
	doctype = "RetailEdge Cashier Expense"

	def __init__(self, *, docstatus: int = 0, modified: str = "2026-10-08 09:00:00"):
		super().__init__(
			name="RE-CE-DRAFT-EDIT-0001",
			docstatus=docstatus,
			expense_status="Draft" if docstatus == 0 else "Submitted",
			company="Demo Company",
			branch="Ketu",
			cashier="cashier@example.com",
			expense_category="Transport",
			amount=500.0,
			description="Initial description",
			expense_date="2026-10-08",
			modified=modified,
			available_shift_cash_after_expense=4500.0,
			save_calls=0,
		)

	def save(self):
		self.save_calls += 1
		self.available_shift_cash_after_expense = 4000.0
		return self


class CashierExpenseEditableDraftTests(unittest.TestCase):
	@patch("retailedge.guided_cashier_expense._assert_active_category")
	@patch("retailedge.guided_cashier_expense.frappe.has_permission", return_value=True)
	@patch("retailedge.guided_cashier_expense.frappe.get_doc")
	def test_guided_update_edits_same_draft_and_ignores_context_spoofing(
		self,
		mock_get_doc,
		_mock_permission,
		mock_category,
	):
		doc = _EditableDraft()
		mock_get_doc.return_value = doc

		result = update_guided_cashier_expense_draft(
			doc.name,
			{
				"expense_category": "Fuel",
				"amount": 1000,
				"description": "Generator fuel",
				"expense_date": "2026-10-08",
				"company": "Spoof Company",
				"branch": "Spoof Branch",
				"payment_account": "Spoof Account",
			},
			expected_modified=doc.modified,
		)

		mock_get_doc.assert_called_once_with("RetailEdge Cashier Expense", doc.name)
		mock_category.assert_called_once_with("Fuel")
		self.assertEqual(doc.save_calls, 1)
		self.assertEqual(doc.expense_category, "Fuel")
		self.assertEqual(doc.amount, 1000.0)
		self.assertEqual(doc.description, "Generator fuel")
		self.assertEqual(doc.company, "Demo Company")
		self.assertEqual(doc.branch, "Ketu")
		self.assertFalse(hasattr(doc, "payment_account"))
		self.assertEqual(result["name"], doc.name)
		self.assertEqual(result["available_cash_after"], 4000.0)

	@patch("retailedge.guided_cashier_expense.frappe.get_doc")
	def test_guided_update_rejects_submitted_expense(self, mock_get_doc):
		mock_get_doc.return_value = _EditableDraft(docstatus=1)

		with self.assertRaises(frappe.ValidationError):
			update_guided_cashier_expense_draft(
				"RE-CE-DRAFT-EDIT-0001",
				{"expense_category": "Fuel", "amount": 1000},
			)

	@patch("retailedge.guided_cashier_expense.frappe.has_permission", return_value=True)
	@patch("retailedge.guided_cashier_expense.frappe.get_doc")
	def test_guided_update_rejects_stale_draft_snapshot(self, mock_get_doc, _mock_permission):
		mock_get_doc.return_value = _EditableDraft(modified="2026-10-08 09:05:00")

		with self.assertRaises(frappe.ValidationError):
			update_guided_cashier_expense_draft(
				"RE-CE-DRAFT-EDIT-0001",
				{"expense_category": "Fuel", "amount": 1000},
				expected_modified="2026-10-08 09:00:00",
			)

	def test_guided_modal_keeps_saved_draft_fields_editable(self):
		source = SIMPLE_DIALOG.read_text(encoding="utf-8")

		self.assertNotIn('v-else-if="draftSaved" class="guided-expense-saved"', source)
		self.assertIn('<form v-else class="guided-expense-form"', source)
		self.assertIn('v-if="draftSaved" class="guided-expense-saved"', source)
		self.assertIn("Save Changes", source)
		self.assertIn("update_guided_cashier_expense_draft", source)
		self.assertIn("async persistDraftChanges()", source)
		self.assertIn("if (this.hasUnsavedChanges) await this.persistDraftChanges();", source)
		self.assertIn('confirmAboveEdgeModal("Discard the unsaved Cashier Expense changes?', source)

	def test_saved_draft_dirty_state_is_not_suppressed(self):
		source = SIMPLE_DIALOG.read_text(encoding="utf-8")
		start = source.index("hasUnsavedChanges()")
		end = source.index("},\n\t},\n\twatch:", start)
		segment = source[start:end]

		self.assertIn("JSON.stringify(this.values) !== this.initialValuesSnapshot", segment)
		self.assertNotIn("if (this.draftSaved) return false", segment)


if __name__ == "__main__":
	unittest.main()
