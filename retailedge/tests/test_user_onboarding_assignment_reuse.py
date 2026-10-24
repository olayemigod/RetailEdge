from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge import user_onboarding


USER = "cashier@example.com"
COMPANY = "RetailEdge Consulting"
BRANCH = "Ketu"


def payload(**overrides):
	values = {
		"mode": "existing",
		"user": USER,
		"role": "RetailEdgeCashier",
		"branch_role": "Cashier",
		"company": COMPANY,
		"branch": BRANCH,
		"effective_from": "2026-10-23",
		"is_primary": True,
		"requires_pos": False,
		"send_welcome_email": False,
	}
	values.update(overrides)
	return values


class TestUserOnboardingAssignmentReuse(unittest.TestCase):
	@patch("retailedge.user_onboarding.create_branch_assignment")
	@patch("retailedge.user_onboarding._assert_assignment_create")
	@patch("retailedge.user_onboarding.get_active_branch_assignments")
	def test_same_branch_reuse_requires_matching_responsibility_and_primary_status(
		self,
		mock_assignments,
		mock_assert_create,
		mock_create,
	):
		mock_assignments.return_value = [
			frappe._dict(
				name="RE-BA-0001",
				company=COMPANY,
				branch=BRANCH,
				branch_role="Manager",
				is_primary=0,
			)
		]

		with self.assertRaises(frappe.ValidationError):
			user_onboarding._ensure_branch_assignment(user=USER, values=payload())

		mock_assert_create.assert_not_called()
		mock_create.assert_not_called()

	@patch("retailedge.user_onboarding.create_branch_assignment")
	@patch("retailedge.user_onboarding._assert_assignment_create")
	@patch("retailedge.user_onboarding.get_active_branch_assignments")
	def test_same_branch_reuse_accepts_matching_responsibility_and_primary_status(
		self,
		mock_assignments,
		mock_assert_create,
		mock_create,
	):
		mock_assignments.return_value = [
			frappe._dict(
				name="RE-BA-0001",
				company=COMPANY,
				branch=BRANCH,
				branch_role="Cashier",
				is_primary=1,
			)
		]

		name, created = user_onboarding._ensure_branch_assignment(user=USER, values=payload())

		self.assertEqual(name, "RE-BA-0001")
		self.assertFalse(created)
		mock_assert_create.assert_not_called()
		mock_create.assert_not_called()


if __name__ == "__main__":
	unittest.main()
