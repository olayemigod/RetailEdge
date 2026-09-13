from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.project_budget import get_project_budget_context


class TestProjectBudget(unittest.TestCase):
	@patch("retailedge.project_budget.frappe.has_permission", return_value=True)
	@patch("retailedge.project_budget.frappe.get_list")
	@patch("retailedge.project_budget.frappe.db.exists", return_value=True)
	@patch("retailedge.project_budget.frappe.get_doc")
	def test_project_budget_context_uses_erpnext_project_budget_truth(
		self,
		mock_get_doc,
		_mock_exists,
		mock_get_list,
		_mock_permission,
	):
		mock_get_doc.return_value = SimpleNamespace(name="PROJ-0001", company="Demo Company")
		mock_get_list.return_value = [
			frappe._dict(
				name="BUDGET-0001", docstatus=1, company="Demo Company", project="PROJ-0001",
				account="Project Expense - DC", budget_amount=500000, from_fiscal_year="2026",
				to_fiscal_year="2026", distribution_frequency="Monthly",
				applicable_on_material_request=1, action_if_annual_budget_exceeded_on_mr="Stop",
				applicable_on_purchase_order=1, action_if_annual_budget_exceeded_on_po="Warn",
				applicable_on_booking_actual_expenses=1, action_if_annual_budget_exceeded="Stop",
				applicable_on_cumulative_expense=1, action_if_annual_exceeded_on_cumulative_expense="Stop",
			),
			frappe._dict(
				name="BUDGET-0002", docstatus=0, company="Demo Company", project="PROJ-0001",
				account="Travel - DC", budget_amount=100000, from_fiscal_year="2026",
				to_fiscal_year="2026", distribution_frequency="Monthly",
				applicable_on_material_request=0, action_if_annual_budget_exceeded_on_mr="",
				applicable_on_purchase_order=0, action_if_annual_budget_exceeded_on_po="",
				applicable_on_booking_actual_expenses=0, action_if_annual_budget_exceeded="",
				applicable_on_cumulative_expense=0, action_if_annual_exceeded_on_cumulative_expense="",
			),
		]

		context = get_project_budget_context("PROJ-0001", limit=20)

		self.assertTrue(context["available"])
		self.assertTrue(context["readable"])
		self.assertEqual(context["submitted_budget"], 500000)
		self.assertEqual(context["draft_budget"], 100000)
		self.assertEqual(context["controlled_budget_count"], 1)
		self.assertIn("Material Request: Stop", context["budgets"][0]["controls"])
		self.assertIn("Purchase Order: Warn", context["budgets"][0]["controls"])
		self.assertEqual(context["source_of_truth"], "ERPNext Budget")
		kwargs = mock_get_list.call_args.kwargs
		self.assertEqual(kwargs["filters"]["budget_against"], "Project")
		self.assertEqual(kwargs["filters"]["project"], "PROJ-0001")
		self.assertEqual(kwargs["filters"]["company"], "Demo Company")

	@patch("retailedge.project_budget.frappe.has_permission")
	@patch("retailedge.project_budget.frappe.db.exists", return_value=True)
	@patch("retailedge.project_budget.frappe.get_doc")
	def test_budget_read_permission_fails_closed_without_exposing_rows(self, mock_get_doc, _mock_exists, mock_permission):
		mock_get_doc.return_value = SimpleNamespace(name="PROJ-0001", company="Demo Company")
		mock_permission.side_effect = lambda doctype, ptype, doc=None: doctype == "Project"
		context = get_project_budget_context("PROJ-0001")
		self.assertTrue(context["available"])
		self.assertFalse(context["readable"])
		self.assertEqual(context["budgets"], [])
		self.assertFalse(context["can_create_budget"])

	@patch("retailedge.project_budget.frappe.has_permission", return_value=True)
	@patch("retailedge.project_budget.frappe.get_list", return_value=[])
	@patch("retailedge.project_budget.frappe.db.exists", return_value=True)
	@patch("retailedge.project_budget.frappe.get_doc")
	def test_budget_limit_is_bounded(self, mock_get_doc, _mock_exists, mock_get_list, _mock_permission):
		mock_get_doc.return_value = SimpleNamespace(name="PROJ-0001", company="Demo Company")
		get_project_budget_context("PROJ-0001", limit=5000)
		self.assertEqual(mock_get_list.call_args.kwargs["limit_page_length"], 200)


if __name__ == "__main__":
	unittest.main()
