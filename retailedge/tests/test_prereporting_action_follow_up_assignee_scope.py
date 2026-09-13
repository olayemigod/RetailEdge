from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import action_follow_up, action_follow_up_query


class TestPrereportingActionFollowUpAssigneeScope(unittest.TestCase):
	def test_search_and_backend_share_one_assignment_scope_decision(self):
		query_source = inspect.getsource(action_follow_up_query._is_assignable_user)
		backend_source = inspect.getsource(action_follow_up._validate_assignment_user)
		self.assertIn("_assignment_scope_decision", query_source)
		self.assertIn("_assignment_scope_decision", backend_source)
		for source in (query_source, backend_source):
			self.assertNotIn("get_user_allowed_branches", source)
			self.assertNotIn("user_has_global_branch_access", source)
			self.assertNotIn("validate_user_branch_access", source)

	def test_missing_company_fails_closed_without_scope_resolution(self):
		with patch("retailedge.reporting_scope.validate_report_scope") as validate_scope:
			decision = action_follow_up._assignment_scope_decision(
				"candidate@example.com",
				company="",
				branch="Main",
			)

		self.assertEqual(decision, action_follow_up.ASSIGNMENT_SCOPE_MISSING_COMPANY)
		validate_scope.assert_not_called()

	def test_owner_scope_is_required_before_branch_scope(self):
		with (
			patch.object(action_follow_up, "_has_owner_financial_access", return_value=False),
			patch("retailedge.reporting_scope.validate_report_scope") as validate_scope,
		):
			decision = action_follow_up._assignment_scope_decision(
				"candidate@example.com",
				company="Scope Co",
				branch="Main",
				require_owner_scope=True,
			)

		self.assertEqual(decision, action_follow_up.ASSIGNMENT_SCOPE_OWNER_REQUIRED)
		validate_scope.assert_not_called()

	def test_explicit_branch_is_revalidated_for_candidate_user(self):
		with patch(
			"retailedge.reporting_scope.validate_report_scope",
			return_value={"restricted": True, "allowed_branches": ["Main"], "branch": "Main"},
		) as validate_scope:
			decision = action_follow_up._assignment_scope_decision(
				"candidate@example.com",
				company="Scope Co",
				branch="Main",
			)

		self.assertEqual(decision, action_follow_up.ASSIGNMENT_SCOPE_ALLOWED)
		validate_scope.assert_called_once_with(
			company="Scope Co",
			branch="Main",
			user="candidate@example.com",
			require_branch_when_restricted=False,
		)

	def test_scope_validation_failure_is_denied(self):
		with patch(
			"retailedge.reporting_scope.validate_report_scope",
			side_effect=frappe.PermissionError,
		):
			decision = action_follow_up._assignment_scope_decision(
				"candidate@example.com",
				company="Scope Co",
				branch="Other",
			)

		self.assertEqual(decision, action_follow_up.ASSIGNMENT_SCOPE_DENIED)

	def test_restricted_blank_scope_is_never_assignable(self):
		with patch(
			"retailedge.reporting_scope.validate_report_scope",
			return_value={"restricted": True, "allowed_branches": ["Main"]},
		):
			decision = action_follow_up._assignment_scope_decision(
				"candidate@example.com",
				company="Scope Co",
				branch="",
			)

		self.assertEqual(decision, action_follow_up.ASSIGNMENT_SCOPE_DENIED)

	def test_company_level_assignment_requires_unrestricted_reporting_scope(self):
		for restricted, expected in (
			(True, action_follow_up.ASSIGNMENT_SCOPE_GLOBAL_REQUIRED),
			(False, action_follow_up.ASSIGNMENT_SCOPE_ALLOWED),
		):
			with self.subTest(restricted=restricted):
				with patch(
					"retailedge.reporting_scope.validate_report_scope",
					return_value={"restricted": restricted, "allowed_branches": ["Main"]},
				):
					decision = action_follow_up._assignment_scope_decision(
						"candidate@example.com",
						company="Scope Co",
						branch="",
						require_global_scope=True,
					)

				self.assertEqual(decision, expected)

	def test_query_and_backend_agree_for_allowed_and_denied_scope(self):
		for decision, expected in (
			(action_follow_up.ASSIGNMENT_SCOPE_ALLOWED, True),
			(action_follow_up.ASSIGNMENT_SCOPE_DENIED, False),
		):
			with self.subTest(decision=decision):
				with (
					patch.object(action_follow_up, "_has_action_center_role", return_value=True),
					patch.object(action_follow_up, "_assignment_scope_decision", return_value=decision),
					patch.object(action_follow_up.frappe.db, "get_value", return_value=1),
				):
					search_allowed = action_follow_up_query._is_assignable_user(
						"candidate@example.com",
						company="Scope Co",
						branch="Main",
						require_global_scope=False,
						require_owner_scope=False,
					)
					if expected:
						action_follow_up._validate_assignment_user(
							"candidate@example.com",
							company="Scope Co",
							branch="Main",
						)
					else:
						with self.assertRaises(frappe.PermissionError):
							action_follow_up._validate_assignment_user(
								"candidate@example.com",
								company="Scope Co",
								branch="Main",
							)
				self.assertEqual(search_allowed, expected)

	def test_candidate_search_remains_permission_aware_and_bounded(self):
		source = inspect.getsource(action_follow_up_query.get_assignable_users)
		self.assertIn("frappe.get_list", source)
		self.assertIn("MAX_CANDIDATES", source)
		self.assertIn("MAX_PAGE_LENGTH", source)
		self.assertNotIn("frappe.get_all", source)
		self.assertNotIn("ignore_permissions", source)

	def test_follow_up_state_transition_contract_is_unchanged(self):
		source = inspect.getsource(action_follow_up.update_action_follow_up)
		for action in ('"acknowledge"', '"snooze"', '"assign"', '"schedule"', '"reopen"'):
			self.assertIn(action, source)
		self.assertIn("get_business_control_center", source)
		self.assertIn("visible = next", source)
		self.assertIn("_validate_assignment_user", source)


if __name__ == "__main__":
	unittest.main()
