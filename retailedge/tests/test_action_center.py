from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge import action_center


class TestActionCenter(unittest.TestCase):
	def setUp(self):
		frappe.session.user = "Administrator"

	@patch("retailedge.action_center.get_supplier_payables")
	@patch("retailedge.action_center.get_customer_receivables")
	@patch("retailedge.action_center.get_cash_shift_verification")
	@patch("retailedge.action_center.get_expense_register")
	@patch("retailedge.action_center.get_owner_dashboard_data")
	def test_composes_existing_exception_sources_without_mutation(
		self, owner, expenses, cash, receivables, payables
	):
		owner.return_value = {
			"attention": [
				{
					"section": "stock",
					"label": "Items are out of stock",
					"value": 3,
					"datatype": "Int",
					"tone": "warning",
					"route": "/app/stock-position",
					"time_basis": "current",
				}
			]
		}
		expenses.return_value = {
			"summary": [
				{"label": "Posting Blocked", "value": 2, "datatype": "Int"},
				{"label": "Submitted for Review", "value": 4, "datatype": "Int"},
			]
		}
		cash.return_value = {"summary": [{"label": "Exceptions", "value": 1, "datatype": "Int"}]}
		receivables.return_value = {
			"summary": [
				{"label": "Overdue", "value": 450000, "datatype": "Currency"},
				{"label": "Over 90 Days", "value": 150000, "datatype": "Currency"},
			],
			"rows": [{"overdue_days": 117}],
		}
		payables.return_value = {
			"summary": [
				{"label": "Overdue", "value": 220000, "datatype": "Currency"},
				{"label": "Over 90 Days", "value": 0, "datatype": "Currency"},
			],
			"rows": [{"overdue_days": 32}],
		}
		result = action_center.get_action_center_data(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-19"}
		)
		self.assertTrue(result["metadata"]["read_only"])
		self.assertEqual(result["metadata"]["resolution_model"], "drill_through_to_existing_workflow_or_report")
		self.assertTrue(any(row["kind"] == "cash_control" for row in result["items"]))
		self.assertTrue(any(row["kind"] == "review_or_posting" for row in result["items"]))
		self.assertTrue(any(row["source"] == "stock" for row in result["items"]))
		receivable_action = next(row for row in result["items"] if row["kind"] == "overdue_receivables")
		payable_action = next(row for row in result["items"] if row["kind"] == "overdue_payables")
		self.assertEqual(receivable_action["severity"], "danger")
		self.assertEqual(receivable_action["exposure"], 450000)
		self.assertEqual(receivable_action["aged_exposure"], 150000)
		self.assertEqual(receivable_action["age_days"], 117)
		self.assertEqual(payable_action["severity"], "warning")
		self.assertEqual(payable_action["exposure"], 220000)
		self.assertEqual(result["items"][0]["severity"], "danger")

	def test_financial_exposure_ignores_current_balances_without_overdue_amount(self):
		items = []
		action_center._action_from_financial_exposure(
			items,
			payload={
				"summary": [
					{"label": "Overdue", "value": 0, "datatype": "Currency"},
					{"label": "Over 90 Days", "value": 0, "datatype": "Currency"},
				],
				"rows": [],
			},
			source="receivables",
			label="Customer receivables are overdue",
			route="/app/customer-receivables",
			kind="overdue_receivables",
		)
		self.assertEqual(items, [])

	def test_dedupe_and_sort_prioritises_danger(self):
		items = [
			{"source": "stock", "label": "Low", "route": "/a", "severity": "warning"},
			{"source": "cash", "label": "Critical", "route": "/b", "severity": "danger"},
			{"source": "stock", "label": "Low", "route": "/a", "severity": "warning"},
		]
		result = action_center._dedupe_and_sort(items)
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["severity"], "danger")

	def test_follow_up_filters_use_effective_status_assignment_and_due_state(self):
		items = [
			{"label": "Mine due", "follow_up": {"effective_status": "Open", "assigned_to": "Administrator", "is_due": True}},
			{"label": "Other due", "follow_up": {"effective_status": "Open", "assigned_to": "other@example.com", "is_due": True}},
			{"label": "Mine acknowledged", "follow_up": {"effective_status": "Acknowledged", "assigned_to": "Administrator", "is_due": False}},
			{"label": "Mine snoozed", "follow_up": {"effective_status": "Snoozed", "assigned_to": "Administrator", "is_due": False}},
		]
		result = action_center._apply_follow_up_filters(
			items,
			follow_up_status="Open",
			assignment_scope="mine",
			due_scope="due",
		)
		self.assertEqual([row["label"] for row in result], ["Mine due"])

	def test_invalid_management_filter_values_fall_back_safely(self):
		self.assertEqual(action_center._choice("Resolved", action_center.FOLLOW_UP_STATUSES, "All"), "All")
		self.assertEqual(action_center._choice("everyone", action_center.ASSIGNMENT_SCOPES, "all"), "all")
		self.assertEqual(action_center._choice("tomorrow", action_center.DUE_SCOPES, "all"), "all")

	@patch("retailedge.action_center.get_supplier_payables", side_effect=frappe.PermissionError)
	@patch("retailedge.action_center.get_customer_receivables", side_effect=frappe.PermissionError)
	@patch("retailedge.action_center.get_owner_dashboard_data", side_effect=frappe.PermissionError)
	@patch("retailedge.action_center.get_expense_register", side_effect=frappe.PermissionError)
	@patch("retailedge.action_center.get_cash_shift_verification", side_effect=frappe.PermissionError)
	def test_permission_denied_sources_are_not_leaked(
		self, cash, expenses, owner, receivables, payables
	):
		result = action_center.get_action_center_data(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-19"}
		)
		self.assertEqual(result["items"], [])
		for source in ("owner", "expenses", "cash_shift", "receivables", "payables"):
			self.assertFalse(result["sources"][source]["available"])

	def test_validation_failure_isolated_to_one_source(self):
		result = action_center._safe_source(
			"receivables",
			lambda: (_ for _ in ()).throw(frappe.ValidationError("scope too broad")),
		)
		self.assertFalse(result["available"])
		self.assertNotIn("scope too broad", result["reason"])

	def test_source_contains_no_transaction_completion_calls(self):
		from pathlib import Path

		source = Path(action_center.__file__).read_text(encoding="utf-8")
		for forbidden in (".submit(", "apply_workflow(", "ignore_permissions=True", "frappe.db.commit("):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
