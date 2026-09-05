from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import procurement_tracker_handoff as handoff

APP_ROOT = Path(__file__).resolve().parents[1]


class TestPrereportingProcurementTrackerScope(unittest.TestCase):
	def _call(
		self,
		*,
		company: str = "Scope Co",
		branch: str = "",
		unrestricted: bool = True,
	):
		with (
			patch.object(handoff, "_resolve_company", return_value=company),
			patch.object(handoff, "_can_open_report", return_value=True),
			patch.object(
				handoff,
				"has_unrestricted_report_scope",
				return_value=unrestricted,
			) as scope,
			patch.object(handoff, "validate_report_scope") as validate_scope,
			patch.object(handoff.frappe, "has_permission", return_value=True),
		):
			result = handoff.get_procurement_tracker_handoff(
				company=company,
				branch=branch,
			)
		return result, scope, validate_scope

	def test_company_wide_availability_uses_selected_company_scope(self):
		result, scope, validate_scope = self._call()

		self.assertTrue(result["available"])
		scope.assert_called_once_with("Scope Co", user=frappe.session.user)
		validate_scope.assert_not_called()
		self.assertEqual(
			result["branch_policy"],
			"unrestricted-company-scope-and-no-selected-branch",
		)

	def test_compatible_unrestricted_legacy_reader_remains_available(self):
		result, _scope, _validate_scope = self._call(unrestricted=True)

		self.assertTrue(result["available"])
		self.assertEqual(result["source_of_truth"], "ERPNext Procurement Tracker Script Report")

	def test_restricted_company_scope_hides_native_handoff(self):
		result, scope, validate_scope = self._call(unrestricted=False)

		self.assertFalse(result["available"])
		self.assertIn("Branch-restricted", result["reason"])
		scope.assert_called_once_with("Scope Co", user=frappe.session.user)
		validate_scope.assert_not_called()

	def test_selected_branch_is_revalidated_by_reporting_scope(self):
		result, scope, validate_scope = self._call(branch="Main")

		self.assertFalse(result["available"])
		self.assertIn("Clear the Branch filter", result["reason"])
		validate_scope.assert_called_once_with(
			company="Scope Co",
			branch="Main",
			user=frappe.session.user,
		)
		scope.assert_called_once_with("Scope Co", user=frappe.session.user)

	def test_invalid_explicit_branch_denial_is_not_suppressed(self):
		with (
			patch.object(handoff, "_resolve_company", return_value="Scope Co"),
			patch.object(handoff, "validate_report_scope", side_effect=frappe.PermissionError),
			patch.object(handoff, "_can_open_report") as report,
		):
			with self.assertRaises(frappe.PermissionError):
				handoff.get_procurement_tracker_handoff(
					company="Scope Co",
					branch="Other",
				)

		report.assert_not_called()

	def test_missing_company_fails_closed_without_scope_resolution(self):
		result, scope, validate_scope = self._call(company="")

		self.assertFalse(result["available"])
		self.assertIn("Choose a Company", result["reason"])
		scope.assert_not_called()
		validate_scope.assert_not_called()

	def test_handoff_remains_capability_only_and_never_executes_report(self):
		source = inspect.getsource(handoff)
		self.assertIn("has_unrestricted_report_scope", source)
		self.assertIn("validate_report_scope", source)
		self.assertNotIn("user_has_global_branch_access", source)
		self.assertNotIn("validate_user_branch_access", source)
		self.assertNotIn("erpnext.buying.report.procurement_tracker", source)
		self.assertNotIn("execute(", source)
		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn("ignore_permissions", source)

	def test_native_route_and_purchasing_composition_are_unchanged(self):
		component = (
			APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchasing.vue"
		).read_text(encoding="utf-8")
		self.assertEqual(handoff.PROCUREMENT_TRACKER_REPORT, "Procurement Tracker")
		self.assertIn("get_procurement_tracker_handoff", component)
		self.assertIn("frappe.route_options = { company:", component)
		self.assertIn('frappe.set_route("query-report"', component)
		self.assertIn("prepare_request_for_quotation_draft", component)
		self.assertIn("prepare_purchase_receipt_draft", component)


if __name__ == "__main__":
	unittest.main()
