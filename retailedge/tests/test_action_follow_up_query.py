from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge import action_follow_up
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
				require_owner_scope=False,
			)
		)

	@patch(
		"retailedge.action_follow_up._assignment_scope_decision",
		return_value=action_follow_up.ASSIGNMENT_SCOPE_GLOBAL_REQUIRED,
	)
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	def test_company_level_warning_requires_global_branch_scope(self, _has_role, _scope):
		self.assertFalse(
			_is_assignable_user(
				"manager@example.com",
				company="Example Co",
				branch="",
				require_global_scope=True,
				require_owner_scope=False,
			)
		)

	@patch(
		"retailedge.action_follow_up._assignment_scope_decision",
		return_value=action_follow_up.ASSIGNMENT_SCOPE_DENIED,
	)
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	def test_branch_assignment_rejects_user_outside_branch_scope(self, _has_role, _scope):
		self.assertFalse(
			_is_assignable_user(
				"manager@example.com",
				company="Example Co",
				branch="Abuja",
				require_global_scope=False,
				require_owner_scope=False,
			)
		)

	@patch(
		"retailedge.action_follow_up._assignment_scope_decision",
		return_value=action_follow_up.ASSIGNMENT_SCOPE_ALLOWED,
	)
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	def test_branch_assignment_accepts_valid_user(self, _has_role, _scope):
		self.assertTrue(
			_is_assignable_user(
				"manager@example.com",
				company="Example Co",
				branch="Lagos",
				require_global_scope=False,
				require_owner_scope=False,
			)
		)


if __name__ == "__main__":
	unittest.main()
