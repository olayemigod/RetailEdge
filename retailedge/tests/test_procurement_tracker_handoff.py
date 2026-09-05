from __future__ import annotations

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from retailedge import procurement_tracker_handoff as handoff


class TestProcurementTrackerHandoff(FrappeTestCase):
	def _call(self, *, branch="", report=True, unrestricted=True, po_read=True):
		with (
			patch.object(handoff, "_resolve_company", return_value="Test Company"),
			patch.object(handoff, "_can_open_report", return_value=report),
			patch.object(handoff, "has_unrestricted_report_scope", return_value=unrestricted),
			patch.object(handoff, "validate_report_scope") as validate_branch,
			patch.object(handoff.frappe, "has_permission", return_value=po_read),
		):
			result = handoff.get_procurement_tracker_handoff(company="Test Company", branch=branch)
		return result, validate_branch

	def test_company_wide_unrestricted_user_can_open_native_tracker(self):
		result, validate_branch = self._call()
		self.assertTrue(result["available"])
		self.assertEqual(result["report"], "Procurement Tracker")
		self.assertEqual(result["source_of_truth"], "ERPNext Procurement Tracker Script Report")
		self.assertTrue(result["company_wide_only"])
		validate_branch.assert_not_called()

	def test_branch_restricted_user_cannot_open_native_tracker(self):
		result, _validate_branch = self._call(unrestricted=False)
		self.assertFalse(result["available"])
		self.assertIn("Branch-restricted", result["reason"])

	def test_selected_branch_hides_company_wide_tracker_even_for_global_user(self):
		result, validate_branch = self._call(branch="Lagos")
		self.assertFalse(result["available"])
		self.assertIn("Clear the Branch filter", result["reason"])
		validate_branch.assert_called_once_with(
			company="Test Company",
			branch="Lagos",
			user=handoff.frappe.session.user,
		)

	def test_unreadable_report_is_not_exposed(self):
		result, _validate_branch = self._call(report=False)
		self.assertFalse(result["available"])
		self.assertIn("unavailable", result["reason"])

	def test_purchase_order_read_permission_is_required(self):
		result, _validate_branch = self._call(po_read=False)
		self.assertFalse(result["available"])
		self.assertIn("Purchase Orders", result["reason"])

	def test_module_does_not_import_or_execute_native_tracker_engine(self):
		source = open(handoff.__file__, encoding="utf-8").read()
		self.assertNotIn("erpnext.buying.report.procurement_tracker", source)
		self.assertNotIn("execute(", source)
