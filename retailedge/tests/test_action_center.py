from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge import action_center


class TestActionCenter(unittest.TestCase):
	def setUp(self):
		frappe.session.user = "Administrator"

	@patch("retailedge.action_center.get_bank_exception_summary")
	@patch("retailedge.action_center.get_supplier_payables")
	@patch("retailedge.action_center.get_customer_receivables")
	@patch("retailedge.action_center.get_cash_shift_verification")
	@patch("retailedge.action_center.get_expense_register")
	@patch("retailedge.action_center.get_inventory_action_summary")
	def test_composes_each_authoritative_exception_source_once_without_mutation(
		self, stock, expenses, cash, receivables, payables, bank
	):
		stock.return_value = {
			"summary": [
				{"label": "Negative Stock", "value": 0, "datatype": "Int"},
				{"label": "Out of Stock", "value": 3, "datatype": "Int"},
				{"label": "Fully Reserved", "value": 0, "datatype": "Int"},
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
		bank.return_value = {
			"summary": [
				{"label": "Bank Matches Need Review", "value": 5, "datatype": "Int"},
				{"label": "Ready for Reconciliation", "value": 3, "datatype": "Int"},
				{"label": "Reconciliation Exceptions", "value": 1, "datatype": "Int"},
			],
			"oldest_days": {"needs_review": 9, "ready": 4, "exceptions": 12},
		}
		result = action_center.get_action_center_data(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-19"}
		)

		self.assertTrue(result["metadata"]["read_only"])
		self.assertEqual(result["metadata"]["source_model"], "one_authoritative_provider_per_exception_domain")
		self.assertNotIn("owner", result["sources"])
		self.assertTrue(any(row["kind"] == "cash_control" for row in result["items"]))
		self.assertEqual(len([row for row in result["items"] if row["kind"] == "review_or_posting"]), 2)
		self.assertTrue(any(row["source"] == "stock" for row in result["items"]))

		receivable_action = next(row for row in result["items"] if row["kind"] == "overdue_receivables")
		payable_action = next(row for row in result["items"] if row["kind"] == "overdue_payables")
		bank_exception = next(row for row in result["items"] if row["kind"] == "bank_reconciliation_exception")
		bank_review = next(row for row in result["items"] if row["kind"] == "bank_match_review")
		bank_ready = next(row for row in result["items"] if row["kind"] == "bank_ready_for_reconciliation")

		self.assertEqual(receivable_action["severity"], "danger")
		self.assertEqual(receivable_action["exposure"], 450000)
		self.assertEqual(receivable_action["aged_exposure"], 150000)
		self.assertEqual(receivable_action["age_days"], 117)
		self.assertEqual(receivable_action["target_type"], "Page")
		self.assertEqual(receivable_action["target"], "customer-receivables")
		self.assertEqual(receivable_action["open_mode"], "same_tab")
		self.assertEqual(payable_action["severity"], "warning")
		self.assertEqual(payable_action["exposure"], 220000)
		self.assertEqual(bank_exception["severity"], "danger")
		self.assertEqual(bank_exception["age_days"], 12)
		self.assertEqual(bank_exception["target_type"], "Report")
		self.assertEqual(bank_exception["open_mode"], "new_tab")
		self.assertEqual(bank_review["target_type"], "DocType")
		self.assertEqual(bank_review["open_mode"], "new_tab")
		self.assertEqual(bank_ready["target_type"], "Report")
		self.assertEqual(bank_ready["open_mode"], "new_tab")
		self.assertEqual(result["items"][0]["severity"], "danger")

		stock.assert_called_once()
		expenses.assert_called_once()
		cash.assert_called_once()
		receivables.assert_called_once()
		payables.assert_called_once()
		bank.assert_called_once()

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
			target="customer-receivables",
		)
		self.assertEqual(items, [])

	def test_bank_exceptions_skip_zero_value_cards(self):
		items = []
		action_center._append_bank_exceptions(
			items,
			{
				"summary": [
					{"label": "Bank Matches Need Review", "value": 0, "datatype": "Int"},
					{"label": "Ready for Reconciliation", "value": 0, "datatype": "Int"},
					{"label": "Reconciliation Exceptions", "value": 0, "datatype": "Int"},
				],
				"oldest_days": {},
			},
		)
		self.assertEqual(items, [])

	def test_dedupe_uses_semantic_identity_not_display_label(self):
		items = [
			{
				"source": "receivables",
				"semantic_key": "overdue_receivables",
				"label": "Customer balances are overdue",
				"route": "/app/customer-receivables",
				"severity": "warning",
			},
			{
				"source": "cash",
				"semantic_key": "cash_control",
				"label": "Critical",
				"route": "/b",
				"severity": "danger",
			},
			{
				"source": "receivables",
				"semantic_key": "overdue_receivables",
				"label": "Receivables need attention",
				"route": "/app/customer-receivables",
				"severity": "danger",
			},
		]
		result = action_center._dedupe_and_sort(items)
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["severity"], "danger")
		self.assertEqual(len([row for row in result if row["source"] == "receivables"]), 1)

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

	@patch("retailedge.action_center.get_bank_exception_summary", side_effect=frappe.PermissionError)
	@patch("retailedge.action_center.get_supplier_payables", side_effect=frappe.PermissionError)
	@patch("retailedge.action_center.get_customer_receivables", side_effect=frappe.PermissionError)
	@patch("retailedge.action_center.get_expense_register", side_effect=frappe.PermissionError)
	@patch("retailedge.action_center.get_cash_shift_verification", side_effect=frappe.PermissionError)
	@patch("retailedge.action_center.get_inventory_action_summary", side_effect=frappe.PermissionError)
	def test_permission_denied_sources_are_not_leaked(
		self, stock, cash, expenses, receivables, payables, bank
	):
		result = action_center.get_action_center_data(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-19"}
		)
		self.assertEqual(result["items"], [])
		for source in ("stock_position", "expenses", "cash_shift", "receivables", "payables", "bank_controls"):
			self.assertFalse(result["sources"][source]["available"])

	def test_validation_failure_isolated_to_one_source(self):
		result = action_center._safe_source(
			"receivables",
			lambda: (_ for _ in ()).throw(frappe.ValidationError("scope too broad")),
		)
		self.assertFalse(result["available"])
		self.assertNotIn("scope too broad", result["reason"])

	@patch("retailedge.action_center._validate_operational_scope")
	def test_explicit_branch_is_validated_before_composition(self, validate_scope):
		resolved = action_center._resolve_action_center_branch(
			"Test Company", "Main", user="branch@example.com"
		)
		self.assertEqual(resolved, "Main")
		validate_scope.assert_called_once_with(
			company="Test Company", branch="Main", user="branch@example.com"
		)

	@patch("retailedge.action_center.get_user_allowed_branches")
	@patch("retailedge.action_center.user_has_global_branch_access", return_value=False)
	@patch("retailedge.action_center._validate_operational_scope")
	def test_blank_branch_auto_narrows_to_sole_permitted_branch(
		self, validate_scope, global_access, allowed_branches
	):
		allowed_branches.return_value = {"branches": ["Main"]}
		resolved = action_center._resolve_action_center_branch(
			"Test Company", "", user="branch@example.com"
		)
		self.assertEqual(resolved, "Main")
		validate_scope.assert_called_once_with(
			company="Test Company", branch="", user="branch@example.com"
		)
		global_access.assert_called_once_with(user="branch@example.com")

	@patch("retailedge.action_center.get_user_allowed_branches")
	@patch("retailedge.action_center.user_has_global_branch_access", return_value=False)
	@patch("retailedge.action_center._validate_operational_scope")
	def test_blank_branch_rejects_ambiguous_multi_branch_access(
		self, validate_scope, global_access, allowed_branches
	):
		allowed_branches.return_value = {"branches": ["Main", "North"]}
		with self.assertRaises(frappe.PermissionError):
			action_center._resolve_action_center_branch(
				"Test Company", "", user="branch@example.com"
			)

	@patch(
		"retailedge.action_center._validate_operational_scope",
		side_effect=frappe.PermissionError,
	)
	def test_scope_denial_stops_action_center_before_source_loading(self, validate_scope):
		with self.assertRaises(frappe.PermissionError):
			action_center._resolve_action_center_branch(
				"Other Company", "", user="branch@example.com"
			)
		validate_scope.assert_called_once()

	def test_source_contains_no_transaction_completion_calls(self):
		from pathlib import Path

		source = Path(action_center.__file__).read_text(encoding="utf-8")
		for forbidden in (".submit(", "apply_workflow(", "ignore_permissions=True", "frappe.db.commit("):
			self.assertNotIn(forbidden, source)
		self.assertNotIn("get_owner_dashboard_data", source)
		self.assertIn("get_inventory_action_summary", source)
		self.assertIn("one_authoritative_provider_per_exception_domain", source)
		self.assertIn("_resolve_action_center_branch(", source)
		self.assertIn("_validate_operational_scope", source)


if __name__ == "__main__":
	unittest.main()