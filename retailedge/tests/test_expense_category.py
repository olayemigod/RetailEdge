from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

APP_ROOT = Path(__file__).resolve().parents[1]


class TestRetailEdgeExpenseCategory(unittest.TestCase):
	def _doc(self, **values):
		return frappe.get_doc(
			{
				"doctype": "RetailEdge Expense Category",
				"category_name": values.pop("category_name", "Fuel"),
				"is_active": 1,
				**values,
			}
		)

	def test_company_is_inferred_from_expense_account(self):
		doc = self._doc(expense_account="Fuel Expense - DC")
		account_context = frappe._dict(
			company="Demo Company",
			root_type="Expense",
			is_group=0,
			disabled=0,
		)
		with patch.object(doc, "_get_expense_account_context", return_value=account_context) as mock_context:
			doc.before_validate()
			doc.validate()

		self.assertEqual(doc.company, "Demo Company")
		self.assertGreaterEqual(mock_context.call_count, 1)

	def test_non_expense_account_is_rejected(self):
		doc = self._doc(company="Demo Company", expense_account="Cash - DC")
		account_context = frappe._dict(
			company="Demo Company",
			root_type="Asset",
			is_group=0,
			disabled=0,
		)
		with patch.object(doc, "_get_expense_account_context", return_value=account_context):
			with self.assertRaises(frappe.ValidationError):
				doc.validate()

	def test_cross_company_cost_center_is_rejected(self):
		doc = self._doc(
			company="Demo Company",
			expense_account="Fuel Expense - DC",
			default_cost_center="Other Main - OC",
		)
		account_context = frappe._dict(
			company="Demo Company",
			root_type="Expense",
			is_group=0,
			disabled=0,
		)
		cost_center_context = frappe._dict(company="Other Company", is_group=0)
		with (
			patch.object(doc, "_get_expense_account_context", return_value=account_context),
			patch.object(doc, "_get_cost_center_context", return_value=cost_center_context),
		):
			with self.assertRaises(frappe.ValidationError):
				doc.validate()

	def test_form_filters_accounting_links_and_clears_company_dependents(self):
		source = (
			APP_ROOT
			/ "retailedge"
			/ "doctype"
			/ "retailedge_expense_category"
			/ "retailedge_expense_category.js"
		).read_text()
		self.assertIn('root_type: "Expense"', source)
		self.assertIn("is_group: 0", source)
		self.assertIn('frm.set_value("expense_account", null)', source)
		self.assertIn('frm.set_value("default_cost_center", null)', source)


if __name__ == "__main__":
	unittest.main()
