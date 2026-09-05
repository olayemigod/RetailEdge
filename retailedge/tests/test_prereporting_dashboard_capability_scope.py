from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from retailedge import dashboard_capabilities


class TestPrereportingDashboardCapabilityScope(unittest.TestCase):
	def test_capability_gate_uses_operational_scope_not_legacy_branch_helpers(self):
		source = inspect.getsource(dashboard_capabilities)
		self.assertIn("get_operational_branch_scope", source)
		self.assertIn("validate_operating_branch", source)
		self.assertNotIn("get_user_allowed_branches", source)
		self.assertNotIn("user_has_global_branch_access", source)
		self.assertNotIn("validate_user_branch_access", source)
		self.assertNotIn("_company_branch_count", source)
		self.assertNotIn("ignore_permissions=True", source)

	def test_company_permission_is_checked_before_branch_scope_resolution(self):
		with (
			patch.object(dashboard_capabilities.frappe, "has_permission", return_value=False),
			patch.object(dashboard_capabilities.frappe, "throw", side_effect=RuntimeError("denied")),
			patch.object(dashboard_capabilities, "get_operational_branch_scope") as get_scope,
		):
			with self.assertRaises(RuntimeError):
				dashboard_capabilities._validate_scope(
					company="Scope Co",
					branch="Branch A",
					user="reader@example.com",
				)

		get_scope.assert_not_called()

	def test_branch_without_company_is_rejected(self):
		with (
			patch.object(dashboard_capabilities.frappe, "throw", side_effect=RuntimeError("denied")),
			patch.object(dashboard_capabilities, "get_operational_branch_scope") as get_scope,
		):
			with self.assertRaises(RuntimeError):
				dashboard_capabilities._validate_scope(
					branch="Branch A",
					user="reader@example.com",
				)

		get_scope.assert_not_called()

	def test_explicit_branch_outside_active_assignments_is_rejected(self):
		with (
			patch.object(dashboard_capabilities.frappe, "has_permission", return_value=True),
			patch.object(
				dashboard_capabilities,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(dashboard_capabilities.frappe, "throw", side_effect=RuntimeError("denied")),
			patch.object(dashboard_capabilities, "validate_operating_branch") as validate_branch,
		):
			with self.assertRaises(RuntimeError):
				dashboard_capabilities._validate_scope(
					company="Scope Co",
					branch="Branch B",
					user="reader@example.com",
				)

		validate_branch.assert_not_called()

	def test_explicit_authorised_branch_is_revalidated(self):
		with (
			patch.object(dashboard_capabilities.frappe, "has_permission", return_value=True),
			patch.object(
				dashboard_capabilities,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(dashboard_capabilities, "validate_operating_branch") as validate_branch,
		):
			dashboard_capabilities._validate_scope(
				company="Scope Co",
				branch="Branch A",
				user="reader@example.com",
			)

		validate_branch.assert_called_once_with(
			company="Scope Co",
			branch="Branch A",
			user="reader@example.com",
			throw=True,
		)

	def test_restricted_zero_branch_reader_fails_closed(self):
		with (
			patch.object(dashboard_capabilities.frappe, "has_permission", return_value=True),
			patch.object(
				dashboard_capabilities,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": []},
			),
			patch.object(dashboard_capabilities.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				dashboard_capabilities._validate_scope(
					company="Scope Co",
					user="reader@example.com",
				)

	def test_restricted_nonzero_reader_may_load_unselected_dashboard_shell(self):
		for allowed in (["Branch A"], ["Branch A", "Branch B"]):
			with self.subTest(allowed=allowed):
				with (
					patch.object(dashboard_capabilities.frappe, "has_permission", return_value=True),
					patch.object(
						dashboard_capabilities,
						"get_operational_branch_scope",
						return_value={"restricted": True, "allowed_branches": allowed},
					),
					patch.object(dashboard_capabilities, "validate_operating_branch") as validate_branch,
				):
					dashboard_capabilities._validate_scope(
						company="Scope Co",
						user="reader@example.com",
					)

				validate_branch.assert_not_called()

	def test_unrestricted_reader_keeps_company_wide_dashboard_shell(self):
		with (
			patch.object(dashboard_capabilities.frappe, "has_permission", return_value=True),
			patch.object(
				dashboard_capabilities,
				"get_operational_branch_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
			patch.object(dashboard_capabilities, "validate_operating_branch") as validate_branch,
		):
			dashboard_capabilities._validate_scope(
				company="Scope Co",
				user="manager@example.com",
			)

		validate_branch.assert_not_called()

	def test_scope_validation_precedes_role_setting_and_document_capabilities(self):
		source = inspect.getsource(dashboard_capabilities.get_dashboard_capabilities)
		self.assertLess(source.index("_validate_scope"), source.index("_user_roles"))
		self.assertLess(source.index("_validate_scope"), source.index("_setting_enabled"))

	def test_view_print_and_export_reuse_the_same_scope_gate(self):
		require_source = inspect.getsource(dashboard_capabilities.require_dashboard_action)
		self.assertIn("get_dashboard_capabilities", require_source)
		for action in ('"view"', '"print"', '"export"'):
			self.assertIn(action, require_source)


if __name__ == "__main__":
	unittest.main()
