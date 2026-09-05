from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.operating_context import (
	get_operational_branch_scope,
	resolve_operational_branch,
)


class RetailEdgePreReportingOperationalBranchScopeTests(unittest.TestCase):
	def test_assignment_history_is_restricted_even_when_no_branch_is_active(self):
		with (
			patch("retailedge.operating_context.user_has_global_branch_access", return_value=False),
			patch("retailedge.operating_context.has_branch_assignments", return_value=True),
			patch("retailedge.operating_context.get_allowed_operating_branches", return_value=[]),
		):
			scope = get_operational_branch_scope("PISONMART", user="stock@example.com")

		self.assertTrue(scope["restricted"])
		self.assertEqual(scope["allowed_branches"], [])
		self.assertEqual(scope["source"], "branch_assignment")

	def test_legacy_user_without_configured_branch_restriction_remains_unrestricted(self):
		with (
			patch("retailedge.operating_context.user_has_global_branch_access", return_value=False),
			patch("retailedge.operating_context.has_branch_assignments", return_value=False),
			patch("retailedge.operating_context.get_user_allowed_branches", return_value={"branches": []}),
			patch("retailedge.operating_context.get_user_branch_profiles", return_value=[]),
		):
			scope = get_operational_branch_scope("PISONMART", user="legacy@example.com")

		self.assertFalse(scope["restricted"])
		self.assertEqual(scope["source"], "unrestricted_legacy")

	def test_restricted_blank_branch_resolves_only_when_one_branch_is_permitted(self):
		with (
			patch(
				"retailedge.operating_context.get_operational_branch_scope",
				return_value={
					"company": "PISONMART",
					"restricted": True,
					"allowed_branches": ["Lagos"],
					"source": "branch_assignment",
				},
			),
			patch("retailedge.operating_context.validate_operating_branch") as validate_branch,
		):
			resolved = resolve_operational_branch("PISONMART", user="stock@example.com")

		validate_branch.assert_called_once_with(
			company="PISONMART",
			branch="Lagos",
			user="stock@example.com",
			throw=True,
		)
		self.assertEqual(resolved["branch"], "Lagos")

	def test_restricted_blank_branch_requires_selection_when_multiple_are_permitted(self):
		with patch(
			"retailedge.operating_context.get_operational_branch_scope",
			return_value={
				"company": "PISONMART",
				"restricted": True,
				"allowed_branches": ["Lagos", "Ikeja"],
				"source": "branch_assignment",
			},
		):
			with self.assertRaises(frappe.ValidationError):
				resolve_operational_branch("PISONMART", user="stock@example.com")

	def test_restricted_blank_branch_fails_closed_when_none_are_permitted(self):
		with patch(
			"retailedge.operating_context.get_operational_branch_scope",
			return_value={
				"company": "PISONMART",
				"restricted": True,
				"allowed_branches": [],
				"source": "branch_assignment",
			},
		):
			with self.assertRaises(frappe.PermissionError):
				resolve_operational_branch("PISONMART", user="stock@example.com")

	def test_unrestricted_blank_branch_preserves_company_wide_behavior(self):
		with (
			patch(
				"retailedge.operating_context.get_operational_branch_scope",
				return_value={
					"company": "PISONMART",
					"restricted": False,
					"allowed_branches": [],
					"source": "global",
				},
			),
			patch("retailedge.operating_context.validate_operating_branch") as validate_branch,
		):
			resolved = resolve_operational_branch("PISONMART", user="manager@example.com")

		validate_branch.assert_not_called()
		self.assertEqual(resolved["branch"], "")


if __name__ == "__main__":
	unittest.main()
