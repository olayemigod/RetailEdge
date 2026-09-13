from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge import action_follow_up


class TestPrereportingActionFollowUpReadScope(unittest.TestCase):
	def test_direct_read_hooks_use_reporting_scope_not_legacy_branch_helpers(self):
		for hook in (
			action_follow_up.get_permission_query_conditions,
			action_follow_up.has_permission,
		):
			source = inspect.getsource(hook)
			self.assertIn("get_report_branch_scope", source)
			self.assertNotIn("get_user_allowed_branches", source)
			self.assertNotIn("user_has_global_branch_access", source)
			self.assertNotIn("validate_user_branch_access", source)

	def test_company_candidates_are_permission_aware_and_bounded(self):
		with (
			patch.object(
				action_follow_up.frappe, "get_list", return_value=["Allowed Co", "Denied Co"]
			) as get_list,
			patch.object(
				action_follow_up.frappe,
				"has_permission",
				side_effect=lambda _doctype, _ptype, *, doc, user: doc == "Allowed Co",
			),
		):
			companies = action_follow_up._readable_companies("reader@example.com")

		self.assertEqual(companies, ["Allowed Co"])
		get_list.assert_called_once_with(
			"Company",
			pluck="name",
			order_by="name asc",
			limit_page_length=action_follow_up.MAX_DIRECT_SCOPE_COMPANIES,
		)

	def test_direct_query_builds_company_specific_restricted_and_unrestricted_clauses(self):
		def report_scope(company, *, user):
			if company == "Restricted Co":
				return {"restricted": True, "allowed_branches": ["Main", "North"]}
			return {"restricted": False, "allowed_branches": []}

		with (
			patch.object(action_follow_up, "_has_action_center_role", return_value=True),
			patch.object(
				action_follow_up,
				"_readable_companies",
				return_value=["Restricted Co", "Open Co"],
			),
			patch("retailedge.reporting_scope.get_report_branch_scope", side_effect=report_scope),
			patch.object(action_follow_up, "_has_owner_financial_access", return_value=True),
		):
			condition = action_follow_up.get_permission_query_conditions("reader@example.com")

		self.assertIn("`company` = 'Restricted Co'", condition)
		self.assertIn("`branch` = 'Main'", condition)
		self.assertIn("`branch` = 'North'", condition)
		self.assertIn("`company` = 'Open Co'", condition)
		self.assertIn(" OR ", condition)

	def test_company_scope_failure_is_omitted_without_broadening_other_companies(self):
		def report_scope(company, *, user):
			if company == "Denied Co":
				raise frappe.PermissionError
			return {"restricted": False, "allowed_branches": []}

		with (
			patch.object(action_follow_up, "_has_action_center_role", return_value=True),
			patch.object(
				action_follow_up,
				"_readable_companies",
				return_value=["Denied Co", "Allowed Co"],
			),
			patch("retailedge.reporting_scope.get_report_branch_scope", side_effect=report_scope),
			patch.object(action_follow_up, "_has_owner_financial_access", return_value=True),
		):
			condition = action_follow_up.get_permission_query_conditions("reader@example.com")

		self.assertNotIn("Denied Co", condition)
		self.assertIn("Allowed Co", condition)

	def test_zero_resolvable_company_scope_fails_closed(self):
		with (
			patch.object(action_follow_up, "_has_action_center_role", return_value=True),
			patch.object(action_follow_up, "_readable_companies", return_value=[]),
		):
			self.assertEqual(
				action_follow_up.get_permission_query_conditions("reader@example.com"),
				"1=0",
			)

	def test_company_query_permission_failure_fails_closed(self):
		with patch.object(
			action_follow_up.frappe,
			"get_list",
			side_effect=frappe.PermissionError,
		):
			self.assertEqual(action_follow_up._readable_companies("reader@example.com"), [])

	def test_r9_query_entitlement_is_evaluated_for_each_restricted_branch(self):
		with patch.object(
			action_follow_up,
			"_has_owner_financial_access",
			side_effect=lambda _user, *, company, branch="": company == "Scope Co" and branch == "Main",
		):
			clauses = action_follow_up._direct_scope_clauses(
				company="Scope Co",
				scope={"restricted": True, "allowed_branches": ["Main", "North"]},
				user="reader@example.com",
			)

		main_clause = next(clause for clause in clauses if "'Main'" in clause)
		north_clause = next(clause for clause in clauses if "'North'" in clause)
		self.assertNotIn("r9_early_warning", main_clause)
		self.assertIn("r9_early_warning", north_clause)

	def test_form_read_requires_company_permission_before_branch_scope(self):
		doc = SimpleNamespace(company="Denied Co", branch="Main", source="expenses")
		with (
			patch.object(action_follow_up, "_has_action_center_role", return_value=True),
			patch.object(action_follow_up.frappe, "has_permission", return_value=False),
			patch("retailedge.reporting_scope.get_report_branch_scope") as report_scope,
		):
			self.assertFalse(action_follow_up.has_permission(doc, user="reader@example.com"))

		report_scope.assert_not_called()

	def test_restricted_form_read_requires_active_branch_membership(self):
		with (
			patch.object(action_follow_up, "_has_action_center_role", return_value=True),
			patch.object(action_follow_up.frappe, "has_permission", return_value=True),
			patch(
				"retailedge.reporting_scope.get_report_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Main"]},
			),
		):
			for branch, expected in (("Main", True), ("North", False), ("", False)):
				with self.subTest(branch=branch):
					doc = SimpleNamespace(company="Scope Co", branch=branch, source="expenses")
					self.assertEqual(
						action_follow_up.has_permission(doc, user="reader@example.com"),
						expected,
					)

	def test_unrestricted_form_read_retains_company_wide_scope(self):
		doc = SimpleNamespace(company="Scope Co", branch="", source="expenses")
		with (
			patch.object(action_follow_up, "_has_action_center_role", return_value=True),
			patch.object(action_follow_up.frappe, "has_permission", return_value=True),
			patch(
				"retailedge.reporting_scope.get_report_branch_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
		):
			self.assertTrue(action_follow_up.has_permission(doc, user="manager@example.com"))

	def test_r9_query_and_form_reads_require_owner_financial_scope(self):
		doc = SimpleNamespace(company="Scope Co", branch="Main", source="r9_early_warning")
		with (
			patch.object(action_follow_up, "_has_action_center_role", return_value=True),
			patch.object(action_follow_up.frappe, "has_permission", return_value=True),
			patch(
				"retailedge.reporting_scope.get_report_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Main"]},
			),
			patch.object(action_follow_up, "_has_owner_financial_access", return_value=False),
		):
			self.assertFalse(action_follow_up.has_permission(doc, user="reader@example.com"))

	def test_slice_does_not_change_follow_up_mutation_contract(self):
		source = inspect.getsource(action_follow_up.update_action_follow_up)
		self.assertIn("get_business_control_center", source)
		self.assertIn("visible = next", source)
		self.assertIn("_validate_assignment_user", source)
		self.assertIn("retailedge_action_follow_up_api_write", source)


if __name__ == "__main__":
	unittest.main()
