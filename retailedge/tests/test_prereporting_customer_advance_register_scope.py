from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge.retailedge.report.retailedge_customer_advance_register import (
	retailedge_customer_advance_register as report,
)


class TestPrereportingCustomerAdvanceRegisterScope(unittest.TestCase):
	def test_unrestricted_blank_scope_preserves_company_wide_query(self):
		with (
			patch.object(
				report,
				"validate_report_scope",
				return_value={"restricted": False, "allowed_branches": [], "branch": ""},
			) as validate_scope,
			patch.object(
				report, "_require_payment_branch_field", return_value="retailedge_branch"
			) as branch_field,
		):
			fieldname, branch_filter = report._payment_branch_scope(company="Scope Co", branch="")

		self.assertEqual(fieldname, "retailedge_branch")
		self.assertIsNone(branch_filter)
		validate_scope.assert_called_once_with(
			company="Scope Co",
			branch="",
			user=frappe.session.user,
			require_branch_when_restricted=False,
		)
		branch_field.assert_called_once_with(None)

	def test_restricted_single_branch_scope_becomes_scalar(self):
		with (
			patch.object(
				report,
				"validate_report_scope",
				return_value={"restricted": True, "allowed_branches": ["Main"], "branch": ""},
			),
			patch.object(report, "_require_payment_branch_field", return_value="branch") as branch_field,
		):
			fieldname, branch_filter = report._payment_branch_scope(company="Scope Co", branch="")

		self.assertEqual((fieldname, branch_filter), ("branch", "Main"))
		branch_field.assert_called_once_with("Main")

	def test_restricted_multi_branch_scope_becomes_in_predicate(self):
		with (
			patch.object(
				report,
				"validate_report_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Main", "North", "Main", ""],
					"branch": "",
				},
			),
			patch.object(report, "_require_payment_branch_field", return_value="retailedge_branch"),
		):
			fieldname, branch_filter = report._payment_branch_scope(company="Scope Co", branch="")

		self.assertEqual(fieldname, "retailedge_branch")
		self.assertEqual(branch_filter, ["in", ["Main", "North"]])

	def test_explicit_branch_is_revalidated_and_remains_scalar(self):
		with (
			patch.object(
				report,
				"validate_report_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Main", "North"],
					"branch": "North",
				},
			) as validate_scope,
			patch.object(report, "_require_payment_branch_field", return_value="branch"),
		):
			fieldname, branch_filter = report._payment_branch_scope(company="Scope Co", branch="North")

		self.assertEqual((fieldname, branch_filter), ("branch", "North"))
		validate_scope.assert_called_once_with(
			company="Scope Co",
			branch="North",
			user=frappe.session.user,
			require_branch_when_restricted=False,
		)

	def test_restricted_zero_scope_stops_before_payment_query(self):
		with (
			patch.object(report.frappe, "has_permission", return_value=True),
			patch.object(report, "validate_report_scope", side_effect=frappe.PermissionError),
			patch.object(report.frappe, "get_list") as get_list,
		):
			with self.assertRaises(frappe.PermissionError):
				report.execute({"company": "Scope Co"})

		get_list.assert_not_called()

	def test_payment_entry_or_company_read_denial_precedes_scope_resolution(self):
		for denied in ("Payment Entry", "Company"):
			with self.subTest(denied=denied):
				with (
					patch.object(
						report.frappe,
						"has_permission",
						side_effect=lambda doctype, *_args, **_kwargs: doctype != denied,
					),
					patch.object(report, "validate_report_scope") as validate_scope,
					patch.object(report.frappe, "get_list") as get_list,
				):
					with self.assertRaises(frappe.PermissionError):
						report.execute({"company": "Scope Co"})

				validate_scope.assert_not_called()
				get_list.assert_not_called()

	def test_unexpected_restricted_empty_scope_fails_closed(self):
		with (
			patch.object(
				report,
				"validate_report_scope",
				return_value={"restricted": True, "allowed_branches": [], "branch": ""},
			),
			patch.object(report, "_require_payment_branch_field") as branch_field,
		):
			with self.assertRaises(frappe.PermissionError):
				report._payment_branch_scope(company="Scope Co", branch="")

		branch_field.assert_not_called()

	def test_missing_branch_attribution_stops_restricted_query(self):
		with (
			patch.object(report.frappe, "has_permission", return_value=True),
			patch.object(
				report,
				"validate_report_scope",
				return_value={"restricted": True, "allowed_branches": ["Main"], "branch": ""},
			),
			patch.object(report, "_require_payment_branch_field", side_effect=frappe.ValidationError),
			patch.object(report.frappe, "get_list") as get_list,
		):
			with self.assertRaises(frappe.ValidationError):
				report.execute({"company": "Scope Co"})

		get_list.assert_not_called()

	def test_restricted_multi_scope_reaches_bounded_payment_query(self):
		with (
			patch.object(report.frappe, "has_permission", return_value=True),
			patch.object(
				report,
				"validate_report_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Main", "North"],
					"branch": "",
				},
			),
			patch.object(report, "_require_payment_branch_field", return_value="retailedge_branch"),
			patch.object(report.frappe, "get_list", return_value=[]) as get_list,
		):
			report.execute({"company": "Scope Co"})

		query = get_list.call_args.kwargs
		self.assertEqual(query["filters"]["company"], "Scope Co")
		self.assertEqual(query["filters"]["retailedge_branch"], ["in", ["Main", "North"]])
		self.assertIn("retailedge_branch", query["fields"])
		self.assertEqual(query["limit_page_length"], report.MAX_ROWS)

	def test_report_remains_read_only_and_accounting_truth_is_untouched(self):
		source = inspect.getsource(report)
		self.assertIn("validate_report_scope", source)
		self.assertIn("frappe.get_list", source)
		self.assertIn('"unallocated_amount": [">", 0]', source)
		self.assertNotIn("validate_user_branch_access", source)
		for forbidden in (
			"Payment Reconciliation",
			"selected_candidate",
			"locked_candidate",
			"frappe.db.sql",
			"ignore_permissions",
			".insert(",
			".save(",
			".submit(",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
