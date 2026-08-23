from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.action_follow_up_query import _is_assignable_user


class RetailEdgeActionFollowUpQueryTests(unittest.TestCase):
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=False)
	def test_rejects_user_without_action_center_role(self, _has_role):
		self.assertFalse(
			_is_assignable_user(
				"user@example.com",
				company="Example Co",
				branch="Lagos",
				require_global_scope=False,
			)
		)

	@patch("retailedge.branch_context.user_has_global_branch_access", return_value=False)
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	def test_company_level_warning_requires_global_branch_scope(self, _has_role, _global_access):
		self.assertFalse(
			_is_assignable_user(
				"manager@example.com",
				company="Example Co",
				branch="",
				require_global_scope=True,
			)
		)

	@patch("retailedge.branch_context.validate_user_branch_access", return_value={"allowed": False})
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	def test_branch_assignment_rejects_user_outside_branch_scope(self, _has_role, _validate_branch):
		self.assertFalse(
			_is_assignable_user(
				"manager@example.com",
				company="Example Co",
				branch="Abuja",
				require_global_scope=False,
			)
		)

	@patch("retailedge.branch_context.validate_user_branch_access", return_value={"allowed": True})
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	def test_branch_assignment_accepts_valid_user(self, _has_role, _validate_branch):
		self.assertTrue(
			_is_assignable_user(
				"manager@example.com",
				company="Example Co",
				branch="Lagos",
				require_global_scope=False,
			)
		)


if __name__ == "__main__":
	unittest.main()
