from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.retailedge.doctype.retailedge_expense_category.retailedge_expense_category import (
	RetailEdgeExpenseCategory,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestRetailEdgeExpenseCategory(unittest.TestCase):
	def _doc(self, **values):
		return RetailEdgeExpenseCategory(
			{
				"doctype": "RetailEdge Expense Category",
				"category_name": values.pop("category_name", "Fuel"),
				"is_active": 1,
				**values,
			}
		)

	@patch("retailedge.retailedge.doctype.retailedge_expense_category.retailedge_expense_category.frappe.db.get_value")
	def test_company_is_inferred_from_expense_account(self, mock_get_value):
		mock_get_value.return_value = frappe._dict(
			company="Demo Company",
			root_type="Expense",
			is_group=0,
			disabled=0,
		)
		doc = self._doc(expense_account="Fuel Expense - DC")

		doc.before_validate()
		doc.validate()

		self.assertEqual(doc.company, "Demo Company")
		self.assertEqual(mock_get_value.call_count, 1)

	@patch("retailedge.retailedge.doctype.retailedge_expense_category.retailedge_expense_category.frappe.db.get_value")
	def test_non_expense_account_is_rejected(self, mock_get_value):
		mock_get_value.return_value = frappe._dict(
			company="Demo Company",
			root_type="Asset",
			is_group=0,
			disabled=0,
		)
		doc = self._doc(company="Demo Company", expense_account="Cash - DC")

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	@patch("retailedge.retailedge.doctype.retailedge_expense_category.retailedge_expense_category.frappe.db.get_value")
	def test_cross_company_cost_center_is_rejected(self, mock_get_value):
		def get_value(doctype, name, fields, as_dict=False):
			if doctype == "Account":
				return frappe._dict(
					company="Demo Company",
					root_type="Expense",
					is_group=0,
					disabled=0,
				)
			if doctype == "Cost Center":
				return frappe._dict(company="Other Company", is_group=0)
			return None

		mock_get_value.side_effect = get_value
		doc = self._doc(
			company="Demo Company",
			expense_account="Fuel Expense - DC",
			default_cost_center="Other Main - OC",
		)

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
