from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge import operating_context


USER = "restricted-branch-user@example.com"
STALE_COMPANY = "RetailEdge Old Company"
ACTIVE_COMPANY = "RetailEdge Current Company"
ACTIVE_BRANCH = "RetailEdge Current Branch"


class TestOperatingContextStaleCompanyRecovery(unittest.TestCase):
	def _active_assignment_rows(self, *, user: str, company: str | None = None):
		self.assertEqual(user, USER)
		if company and company != ACTIVE_COMPANY:
			return []
		return [
			{
				"company": ACTIVE_COMPANY,
				"branch": ACTIVE_BRANCH,
				"is_primary": 1,
			}
		]

	@staticmethod
	def _validated_context(*, company: str, branch: str, user: str, throw: bool):
		return {
			"allowed": True,
			"company": company,
			"branch": branch,
			"reason": "validated",
		}

	@staticmethod
	def _built_context(*, company: str, branch: str, user: str, source: str):
		return {
			"company": company,
			"branch": branch,
			"user": user,
			"source": source,
		}

	def test_passive_stale_company_default_recovers_to_active_primary_assignment(self):
		with (
			patch.object(operating_context.frappe.defaults, "get_user_default", return_value=STALE_COMPANY),
			patch.object(operating_context, "has_branch_assignments", return_value=True),
			patch.object(operating_context, "user_has_global_branch_access", return_value=False),
			patch.object(
				operating_context,
				"get_active_branch_assignments",
				side_effect=self._active_assignment_rows,
			),
			patch.object(operating_context, "_assert_company_access") as assert_company_access,
			patch.object(
				operating_context,
				"_validate_context",
				side_effect=self._validated_context,
			),
			patch.object(
				operating_context,
				"_build_context",
				side_effect=self._built_context,
			),
			patch.object(operating_context, "resolve_branch_from_user") as legacy_fallback,
		):
			context = operating_context._resolve_fallback_context(company="", user=USER)

		self.assertEqual(context["company"], ACTIVE_COMPANY)
		self.assertEqual(context["branch"], ACTIVE_BRANCH)
		self.assertEqual(context["source"], "Branch Assignment")
		assert_company_access.assert_called_once_with(ACTIVE_COMPANY, user=USER)
		legacy_fallback.assert_not_called()

	def test_explicit_inaccessible_company_request_still_fails_closed(self):
		def assert_company_access(company: str, user: str | None = None):
			if company == STALE_COMPANY:
				raise frappe.PermissionError

		with (
			patch.object(operating_context.frappe.defaults, "get_user_default", return_value=ACTIVE_COMPANY),
			patch.object(operating_context, "has_branch_assignments", return_value=True),
			patch.object(operating_context, "user_has_global_branch_access", return_value=False),
			patch.object(
				operating_context,
				"get_active_branch_assignments",
				side_effect=self._active_assignment_rows,
			),
			patch.object(
				operating_context,
				"_assert_company_access",
				side_effect=assert_company_access,
			),
		):
			with self.assertRaises(frappe.PermissionError):
				operating_context._resolve_fallback_context(company=STALE_COMPANY, user=USER)

	def test_restricted_zero_active_assignment_does_not_restore_stale_company(self):
		with (
			patch.object(operating_context.frappe.defaults, "get_user_default", return_value=STALE_COMPANY),
			patch.object(operating_context, "has_branch_assignments", return_value=True),
			patch.object(operating_context, "user_has_global_branch_access", return_value=False),
			patch.object(operating_context, "get_active_branch_assignments", return_value=[]),
			patch.object(operating_context, "_assert_company_access") as assert_company_access,
			patch.object(
				operating_context,
				"_build_context",
				side_effect=self._built_context,
			),
			patch.object(operating_context, "resolve_branch_from_user") as legacy_fallback,
		):
			context = operating_context._resolve_fallback_context(company="", user=USER)

		self.assertEqual(context["company"], "")
		self.assertEqual(context["branch"], "")
		self.assertEqual(context["source"], "branch_assignment")
		assert_company_access.assert_not_called()
		legacy_fallback.assert_not_called()
