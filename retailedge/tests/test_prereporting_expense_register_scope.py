from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import expense_register as register


class TestPrereportingExpenseRegisterReadScope(unittest.TestCase):
	def test_register_uses_cashier_expense_authority_not_legacy_branch_scope(self):
		source = inspect.getsource(register)
		self.assertIn("apply_cashier_expense_read_scope", source)
		self.assertIn("get_operational_branch_scope", source)
		self.assertNotIn("get_branch_query_filters", source)
		self.assertNotIn("validate_user_branch_access", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_query_builder_delegates_company_and_branch_before_other_filters(self):
		with (
			patch.object(register, "_assert_expense_read_access"),
			patch.object(register, "_assert_company_read_access"),
			patch.object(register, "_can_view_other_cashiers", return_value=True),
			patch.object(
				register,
				"apply_cashier_expense_read_scope",
				return_value={"company": "Scope Co", "branch": ["in", ["Branch A", "Branch B"]]},
			) as apply_scope,
		):
			result = register._build_query_filters(
				frappe._dict(
					company="Scope Co",
					from_date="2026-09-01",
					to_date="2026-09-04",
				)
			)

		apply_scope.assert_called_once_with(
			{"company": "Scope Co"},
			user=frappe.session.user,
		)
		self.assertEqual(result["branch"], ["in", ["Branch A", "Branch B"]])
		self.assertEqual(result["expense_date"][0], "between")

	def test_explicit_branch_is_passed_to_authoritative_scope_applicator(self):
		with (
			patch.object(register, "_assert_expense_read_access"),
			patch.object(register, "_assert_company_read_access"),
			patch.object(register, "_can_view_other_cashiers", return_value=True),
			patch.object(
				register,
				"apply_cashier_expense_read_scope",
				return_value={"company": "Scope Co", "branch": "Branch A"},
			) as apply_scope,
		):
			register._build_query_filters(frappe._dict(company="Scope Co", branch="Branch A"))

		apply_scope.assert_called_once_with(
			{"company": "Scope Co", "branch": "Branch A"},
			user=frappe.session.user,
		)

	def test_restricted_context_preserves_valid_candidate(self):
		with patch.object(
			register,
			"get_operational_branch_scope",
			return_value={"restricted": True, "allowed_branches": ["Branch A", "Branch B"]},
		):
			result = register._resolve_context_branch(
				company="Scope Co", candidate="Branch B", user="reader@example.com"
			)
		self.assertEqual(result, "Branch B")

	def test_restricted_context_fills_only_unambiguous_branch(self):
		for allowed, expected in (
			(["Branch A"], "Branch A"),
			(["Branch A", "Branch B"], ""),
			([], ""),
		):
			with self.subTest(allowed=allowed):
				with patch.object(
					register,
					"get_operational_branch_scope",
					return_value={"restricted": True, "allowed_branches": allowed},
				):
					result = register._resolve_context_branch(
						company="Scope Co", candidate="Stale Branch", user="reader@example.com"
					)
				self.assertEqual(result, expected)

	def test_unrestricted_context_preserves_legacy_default_branch(self):
		with patch.object(
			register,
			"get_operational_branch_scope",
			return_value={"restricted": False, "allowed_branches": []},
		):
			result = register._resolve_context_branch(
				company="Scope Co", candidate="Default Branch", user="reader@example.com"
			)
		self.assertEqual(result, "Default Branch")

	def test_branch_search_uses_restricted_assignment_union(self):
		with (
			patch.object(register.frappe, "get_meta") as get_meta,
			patch.object(register.frappe, "get_list", return_value=[]) as get_list,
		):
			get_meta.return_value.has_field.return_value = True
			register._search_branches(
				txt="Branch",
				company="Scope Co",
				scope={"restricted": True, "allowed_branches": ["Branch A", "Branch B"]},
			)

		self.assertEqual(
			get_list.call_args.kwargs["filters"],
			{"company": "Scope Co", "name": ["in", ["Branch A", "Branch B"]]},
		)

	def test_restricted_zero_branch_search_fails_closed(self):
		with patch.object(register.frappe, "get_list") as get_list:
			result = register._search_branches(
				txt="",
				company="Scope Co",
				scope={"restricted": True, "allowed_branches": []},
			)

		self.assertEqual(result, [])
		get_list.assert_not_called()

	def test_unrestricted_branch_search_is_not_interpreted_as_zero_access(self):
		with (
			patch.object(register.frappe, "get_meta") as get_meta,
			patch.object(register.frappe, "get_list", return_value=[]) as get_list,
		):
			get_meta.return_value.has_field.return_value = False
			register._search_branches(
				txt="",
				company="Scope Co",
				scope={"restricted": False, "allowed_branches": []},
			)

		self.assertEqual(get_list.call_args.kwargs["filters"], {})

	def test_non_company_search_requires_company_before_master_read(self):
		with (
			patch.object(register, "_assert_expense_read_access"),
			patch.object(register.frappe.defaults, "get_user_default", return_value=""),
			patch.object(register.frappe, "throw", side_effect=RuntimeError("company required")),
			patch.object(register, "_search_categories") as search_categories,
		):
			with self.assertRaises(RuntimeError):
				register.search_expense_register_options("expense_category", "Fuel")

		search_categories.assert_not_called()

	def test_page_and_export_share_the_same_scope_builder(self):
		for endpoint in (register.get_expense_register, register.get_expense_register_export):
			self.assertIn("_build_query_filters(filters)", inspect.getsource(endpoint))


if __name__ == "__main__":
	unittest.main()
