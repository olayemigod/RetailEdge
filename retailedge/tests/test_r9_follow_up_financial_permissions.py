from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge import action_follow_up
from retailedge.action_follow_up_query import _is_assignable_user


class RetailEdgeR9FollowUpFinancialPermissionTests(unittest.TestCase):
	@patch("retailedge.action_follow_up._has_owner_financial_access", return_value=False)
	@patch("retailedge.reporting_scope.get_report_branch_scope")
	@patch("retailedge.action_follow_up._readable_companies", return_value=["Example Co"])
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	def test_global_operational_user_cannot_list_r9_financial_followups(
		self, _action_role, _companies, report_scope, _owner_access
	):
		report_scope.return_value = {"restricted": False, "allowed_branches": []}
		condition = action_follow_up.get_permission_query_conditions("ops@example.com")
		self.assertIn("source", condition)
		self.assertIn("r9_early_warning", condition)

	@patch(
		"retailedge.reporting_scope.get_report_branch_scope",
		return_value={"restricted": True, "allowed_branches": ["Lagos"]},
	)
	@patch("retailedge.action_follow_up._has_owner_financial_access", return_value=False)
	@patch("retailedge.action_follow_up.frappe.has_permission", return_value=True)
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	def test_direct_r9_followup_form_read_requires_owner_financial_access(
		self, _action_role, _company, _owner_access, _scope
	):
		doc = SimpleNamespace(company="Example Co", branch="Lagos", source="r9_early_warning")
		self.assertFalse(action_follow_up.has_permission(doc, user="ops@example.com"))

	@patch("retailedge.action_follow_up._has_owner_financial_access", return_value=False)
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	@patch("retailedge.action_follow_up.frappe.db.get_value", return_value=1)
	def test_r9_assignment_requires_owner_financial_access(self, _enabled, _action_role, _owner_access):
		with self.assertRaises(frappe.PermissionError):
			action_follow_up._validate_assignment_user(
				"ops@example.com",
				company="Example Co",
				branch="Lagos",
				require_owner_scope=True,
			)

	@patch("retailedge.action_follow_up._has_owner_financial_access", return_value=False)
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	def test_r9_assignee_query_excludes_user_without_owner_financial_access(
		self, _action_role, _owner_access
	):
		self.assertFalse(
			_is_assignable_user(
				"ops@example.com",
				company="Example Co",
				branch="Lagos",
				require_global_scope=False,
				require_owner_scope=True,
			)
		)

	def test_mutation_marks_all_r9_assignments_as_owner_scope(self):
		source = open(action_follow_up.__file__, encoding="utf-8").read()
		self.assertIn("require_owner_scope=is_r9_warning", source)
		self.assertIn('source == "r9_early_warning"', source)


if __name__ == "__main__":
	unittest.main()
