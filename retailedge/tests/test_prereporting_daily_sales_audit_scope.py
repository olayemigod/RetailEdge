from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from retailedge import daily_sales_audit as audit
from retailedge import daily_sales_audit_read_scope as read_scope


class TestPrereportingDailySalesAuditReadScope(unittest.TestCase):
	def _scope_query(self, filters, scope):
		with patch.object(read_scope, "get_operational_branch_scope", return_value=scope):
			return read_scope.apply_daily_sales_audit_query_branch_scope(
				"POS Opening Shift",
				filters,
				branch_field="branch",
				user="reader@example.com",
			)

	def test_restricted_explicit_branch_outside_reader_scope_is_rejected(self):
		with (
			patch.object(
				read_scope,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				read_scope.apply_daily_sales_audit_query_branch_scope(
					"POS Opening Shift",
					{"company": "Scope Co", "branch": "Branch B", "cashier": "cashier@example.com"},
					branch_field="branch",
					user="reader@example.com",
				)

	def test_restricted_single_branch_blank_query_resolves_exactly(self):
		result = self._scope_query(
			{"company": "Scope Co", "cashier": "cashier@example.com"},
			{"restricted": True, "allowed_branches": ["Branch A"]},
		)
		self.assertEqual(result, {"branch": "Branch A"})

	def test_restricted_multi_branch_blank_query_uses_union(self):
		result = self._scope_query(
			{"company": "Scope Co"},
			{"restricted": True, "allowed_branches": ["Branch A", "Branch B"]},
		)
		self.assertEqual(result, {"branch": ["in", ["Branch A", "Branch B"]]})

	def test_restricted_zero_branch_query_fails_closed(self):
		result = self._scope_query(
			{"company": "Scope Co"},
			{"restricted": True, "allowed_branches": []},
		)
		self.assertEqual(result, {"branch": read_scope.NO_BRANCH_SCOPE_SENTINEL})

	def test_unrestricted_blank_branch_preserves_company_wide_scope(self):
		result = self._scope_query(
			{"company": "Scope Co"},
			{"restricted": False, "allowed_branches": []},
		)
		self.assertEqual(result, {})

	def test_operational_query_without_company_does_not_become_cross_company(self):
		result = read_scope.apply_daily_sales_audit_query_branch_scope(
			"POS Opening Shift",
			{"cashier": "cashier@example.com"},
			branch_field="branch",
			user="reader@example.com",
		)
		self.assertIsNone(result)

	def test_branchless_shift_scope_falls_back_to_allowed_branch_pos_profiles(self):
		with (
			patch.object(
				read_scope,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A", "Branch B"]},
			),
			patch.object(
				read_scope,
				"get_enabled_branch_profiles",
				return_value=[
					{"branch": "Branch A", "default_pos_profile": "POS A"},
					{"branch": "Branch B", "default_pos_profile": "POS B"},
					{"branch": "Branch C", "default_pos_profile": "POS C"},
				],
			),
		):
			result = read_scope.apply_daily_sales_audit_query_branch_scope(
				"POS Opening Shift",
				{"company": "Scope Co"},
				branch_field=None,
				pos_profile_scope_field="pos_profile",
				user="reader@example.com",
			)
		self.assertEqual(result, {"pos_profile": ["in", ["POS A", "POS B"]]})

	def test_cashier_inferred_branch_is_revalidated_against_reader(self):
		with (
			patch.object(
				read_scope,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				read_scope.validate_daily_sales_audit_read_context(
					{"company": "Scope Co", "branch": "Branch B", "cashier": "cashier@example.com"},
					selection={"company": "Scope Co", "cashier": "cashier@example.com"},
					user="reader@example.com",
				)

	def test_single_branch_scope_can_fill_blank_singular_context(self):
		with patch.object(
			read_scope,
			"get_operational_branch_scope",
			return_value={"restricted": True, "allowed_branches": ["Branch A"]},
		):
			result = read_scope.validate_daily_sales_audit_read_context(
				{"company": "Scope Co"},
				selection={"company": "Scope Co"},
				require_branch=True,
				user="reader@example.com",
			)
		self.assertEqual(result["branch"], "Branch A")

	def test_multi_branch_scope_requires_branch_for_singular_audit_context(self):
		with (
			patch.object(
				read_scope,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A", "Branch B"]},
			),
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("choose branch")),
		):
			with self.assertRaises(RuntimeError):
				read_scope.validate_daily_sales_audit_read_context(
					{"company": "Scope Co"},
					selection={"company": "Scope Co"},
					require_branch=True,
					user="reader@example.com",
				)

	def test_zero_branch_scope_blocks_singular_audit_context(self):
		with (
			patch.object(
				read_scope,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": []},
			),
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("inactive")),
		):
			with self.assertRaises(RuntimeError):
				read_scope.validate_daily_sales_audit_read_context(
					{"company": "Scope Co"},
					selection={"company": "Scope Co"},
					require_branch=True,
					user="reader@example.com",
				)

	def test_query_builder_uses_authoritative_daily_audit_scope(self):
		source = inspect.getsource(audit._build_query_filters)
		self.assertIn("apply_daily_sales_audit_query_branch_scope", source)
		self.assertNotIn("get_branch_query_filters", source)
		self.assertNotIn('user=filters.get("cashier")', source)

	def test_context_selection_resolver_uses_current_reader_not_selected_cashier_for_access(self):
		source = inspect.getsource(audit.resolve_daily_sales_audit_context_from_selection)
		self.assertIn("user=get_daily_sales_audit_reader()", source)
		self.assertIn("validate_daily_sales_audit_read_context", source)
		self.assertNotIn('user=filters.get("cashier")', source)

	def test_singular_context_revalidates_current_reader_before_transaction_reads(self):
		source = inspect.getsource(audit.get_daily_sales_audit_context)
		branch_start = source.index("branch_context = resolve_retailedge_branch_context")
		branch_end = source.index("settings = get_daily_sales_audit_settings")
		branch_section = source[branch_start:branch_end]
		self.assertIn("user=get_daily_sales_audit_reader()", branch_section)
		self.assertIn("validate_daily_sales_audit_read_context", branch_section)
		self.assertIn("require_branch=True", branch_section)
		self.assertNotIn('user=filters.get("cashier")', branch_section)

	def test_cash_snapshot_keeps_selected_cashier_as_business_subject(self):
		source = inspect.getsource(audit.get_daily_sales_audit_context)
		self.assertIn("get_shift_cash_snapshot", source)
		self.assertIn('user=filters.get("cashier")', source)

	def test_branch_options_use_operating_context_company_binding(self):
		with patch.object(
			audit,
			"get_daily_sales_audit_branch_options",
			return_value=["Branch A", "Branch B"],
		):
			result = audit._list_branches({"company": "Scope Co"})
		self.assertEqual(result, ["Branch A", "Branch B"])

	def test_zero_branch_scope_returns_no_branch_options(self):
		with patch.object(audit, "get_daily_sales_audit_branch_options", return_value=[]):
			result = audit._list_branches({"company": "Scope Co"})
		self.assertEqual(result, [])

	def test_cashier_search_is_derived_from_scoped_operational_cashiers(self):
		source = inspect.getsource(audit.search_daily_sales_audit_cashiers)
		self.assertIn("_list_cashiers", source)
		self.assertNotIn("frappe.get_all(", source)
		self.assertNotIn('"User"', source)

	def test_pos_profile_users_are_not_read_before_profile_scope_validation(self):
		source = inspect.getsource(audit._list_cashiers)
		self.assertLess(source.index("_list_pos_profiles"), source.index("_list_pos_profile_users"))

	def test_shift_search_fails_closed_when_query_scope_cannot_be_built(self):
		with (
			patch.object(audit, "_has_doctype", return_value=True),
			patch.object(audit, "_build_query_filters", return_value=None),
			patch.object(audit.frappe, "get_all") as mock_get_all,
		):
			result = audit._search_daily_sales_audit_shifts(
				"POS Opening Shift", "", 0, 20, {"cashier": "cashier@example.com"}
			)
		self.assertEqual(result, [])
		mock_get_all.assert_not_called()

	def test_review_mutations_are_not_rewired_through_read_scope(self):
		for action in (
			audit.start_daily_sales_audit_review,
			audit.mark_daily_sales_audit_balanced,
			audit.mark_daily_sales_audit_variance_found,
			audit.approve_daily_sales_audit,
			audit.reject_daily_sales_audit,
			audit.reopen_daily_sales_audit,
		):
			self.assertNotIn("apply_daily_sales_audit_query_branch_scope", inspect.getsource(action))


if __name__ == "__main__":
	unittest.main()
