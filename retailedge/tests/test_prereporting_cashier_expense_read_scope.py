from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from retailedge import cashier_expense
from retailedge import cashier_expense_audit
from retailedge import cashier_expense_read_scope as read_scope


class TestPrereportingCashierExpenseReadScope(unittest.TestCase):
	def _apply(self, filters, scope):
		with (
			patch.object(read_scope.frappe, "has_permission", return_value=True),
			patch.object(read_scope, "get_operational_branch_scope", return_value=scope),
		):
			return read_scope.apply_cashier_expense_read_scope(filters, user="reader@example.com")

	def test_restricted_explicit_branch_outside_assignments_is_rejected(self):
		with (
			patch.object(read_scope.frappe, "has_permission", return_value=True),
			patch.object(
				read_scope,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				read_scope.apply_cashier_expense_read_scope(
					{"company": "Scope Co", "branch": "Branch B"},
					user="reader@example.com",
				)

	def test_restricted_single_branch_blank_filter_resolves_to_that_branch(self):
		result = self._apply(
			{"company": "Scope Co", "cashier": "cashier@example.com"},
			{"restricted": True, "allowed_branches": ["Branch A"]},
		)
		self.assertEqual(result["branch"], "Branch A")
		self.assertEqual(result["cashier"], "cashier@example.com")

	def test_restricted_multi_branch_blank_filter_scopes_to_union(self):
		result = self._apply(
			{"company": "Scope Co"},
			{"restricted": True, "allowed_branches": ["Branch A", "Branch B"]},
		)
		self.assertEqual(result["branch"], ["in", ["Branch A", "Branch B"]])

	def test_restricted_zero_branch_scope_fails_closed(self):
		result = self._apply(
			{"company": "Scope Co"},
			{"restricted": True, "allowed_branches": []},
		)
		self.assertEqual(result["branch"], read_scope.NO_BRANCH_SCOPE_SENTINEL)

	def test_unrestricted_blank_branch_preserves_company_wide_scope(self):
		result = self._apply(
			{"company": "Scope Co"},
			{"restricted": False, "allowed_branches": []},
		)
		self.assertEqual(result["company"], "Scope Co")
		self.assertNotIn("branch", result)

	def test_supported_list_filters_keep_shape_and_gain_multi_branch_scope(self):
		filters = [
			[read_scope.CASHIER_EXPENSE_DOCTYPE, "company", "=", "Scope Co"],
			[read_scope.CASHIER_EXPENSE_DOCTYPE, "expense_status", "!=", "Cancelled"],
		]
		result = self._apply(
			filters,
			{"restricted": True, "allowed_branches": ["Branch A", "Branch B"]},
		)
		self.assertIsInstance(result, list)
		self.assertIn(
			[read_scope.CASHIER_EXPENSE_DOCTYPE, "branch", "in", ["Branch A", "Branch B"]],
			result,
		)
		self.assertIn(filters[1], result)

	def test_list_filter_explicit_unauthorised_branch_is_rejected(self):
		filters = [
			[read_scope.CASHIER_EXPENSE_DOCTYPE, "company", "=", "Scope Co"],
			[read_scope.CASHIER_EXPENSE_DOCTYPE, "branch", "=", "Branch B"],
		]
		with (
			patch.object(read_scope.frappe, "has_permission", return_value=True),
			patch.object(
				read_scope,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				read_scope.apply_cashier_expense_read_scope(filters, user="reader@example.com")

	def test_ambiguous_list_branch_predicate_fails_closed(self):
		filters = [
			[read_scope.CASHIER_EXPENSE_DOCTYPE, "company", "=", "Scope Co"],
			[read_scope.CASHIER_EXPENSE_DOCTYPE, "branch", "in", ["Branch A", "Branch B"]],
		]
		with (
			patch.object(read_scope.frappe, "has_permission", return_value=True),
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("invalid")),
		):
			with self.assertRaises(RuntimeError):
				read_scope.apply_cashier_expense_read_scope(filters, user="reader@example.com")

	def test_non_global_user_without_company_fails_closed(self):
		with (
			patch.object(read_scope.frappe, "has_permission", return_value=True),
			patch.object(read_scope.frappe.defaults, "get_user_default", return_value=None),
			patch.object(read_scope, "user_has_global_branch_access", return_value=False),
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("company required")),
		):
			with self.assertRaises(RuntimeError):
				read_scope.apply_cashier_expense_read_scope({}, user="reader@example.com")

	def test_global_user_without_company_retains_legacy_cross_company_compatibility(self):
		with (
			patch.object(read_scope.frappe, "has_permission", return_value=True),
			patch.object(read_scope.frappe.defaults, "get_user_default", return_value=None),
			patch.object(read_scope, "user_has_global_branch_access", return_value=True),
		):
			result = read_scope.apply_cashier_expense_read_scope(
				{"expense_status": "Submitted"}, user="Administrator"
			)
		self.assertEqual(result, {"expense_status": "Submitted"})

	def test_doctype_read_permission_is_required_before_get_all_reads(self):
		with (
			patch.object(read_scope.frappe, "has_permission", return_value=False),
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("no read")),
		):
			with self.assertRaises(RuntimeError):
				read_scope.apply_cashier_expense_read_scope(
					{"company": "Scope Co"}, user="reader@example.com"
				)

	def test_summary_and_variance_builders_no_longer_depend_on_legacy_scope(self):
		for builder in (cashier_expense._build_summary_filters, cashier_expense._build_variance_filters):
			source = inspect.getsource(builder)
			self.assertIn("apply_cashier_expense_read_scope", source)
			self.assertNotIn("get_branch_query_filters", source)

	def test_daily_audit_builder_uses_same_authoritative_read_scope(self):
		source = inspect.getsource(cashier_expense_audit._build_daily_audit_filters)
		self.assertIn("apply_cashier_expense_read_scope", source)
		self.assertNotIn("get_branch_query_filters", source)

	def test_mutation_functions_are_not_rewired_through_read_scope(self):
		for action in (
			cashier_expense.approve_cashier_expense,
			cashier_expense.reject_cashier_expense,
			cashier_expense.reopen_cashier_expense,
			cashier_expense_audit.mark_cashier_expense_included_for_daily_audit,
			cashier_expense_audit.mark_cashier_expense_excluded_from_daily_audit,
			cashier_expense_audit.mark_cashier_expense_needs_clarification,
		):
			self.assertNotIn("apply_cashier_expense_read_scope", inspect.getsource(action))


if __name__ == "__main__":
	unittest.main()
