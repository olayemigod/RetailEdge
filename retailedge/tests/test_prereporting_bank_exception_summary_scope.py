from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import bank_exception_summary as summary


class TestPrereportingBankExceptionSummaryScope(unittest.TestCase):
	def _permissions(self, doctype, *_args, **_kwargs):
		return doctype in {"Company", "RetailEdge Bank Transaction Match"}

	def test_unrestricted_blank_scope_preserves_company_wide_filter(self):
		with (
			patch.object(summary.frappe, "has_permission", side_effect=self._permissions),
			patch.object(
				summary,
				"validate_report_scope",
				return_value={"restricted": False, "allowed_branches": [], "branch": ""},
			) as validate_scope,
		):
			branch_filter = summary._resolve_branch_scope_filter(
				company="Scope Co",
				branch="",
			)

		self.assertIsNone(branch_filter)
		validate_scope.assert_called_once_with(
			company="Scope Co",
			branch="",
			user=frappe.session.user,
			require_branch_when_restricted=False,
		)

	def test_restricted_blank_scope_becomes_allowed_branch_predicate(self):
		with (
			patch.object(summary.frappe, "has_permission", side_effect=self._permissions),
			patch.object(
				summary,
				"validate_report_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Main", "North", "Main", ""],
					"branch": "",
				},
			),
		):
			branch_filter = summary._resolve_branch_scope_filter(
				company="Scope Co",
				branch="",
			)

		self.assertEqual(branch_filter, ["in", ["Main", "North"]])

	def test_explicit_branch_is_revalidated_and_remains_scalar(self):
		with (
			patch.object(summary.frappe, "has_permission", side_effect=self._permissions),
			patch.object(
				summary,
				"validate_report_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Main", "North"],
					"branch": "North",
				},
			) as validate_scope,
		):
			branch_filter = summary._resolve_branch_scope_filter(
				company="Scope Co",
				branch="North",
			)

		self.assertEqual(branch_filter, "North")
		validate_scope.assert_called_once_with(
			company="Scope Co",
			branch="North",
			user=frappe.session.user,
			require_branch_when_restricted=False,
		)

	def test_restricted_zero_scope_stops_before_match_query(self):
		with (
			patch.object(summary.frappe, "has_permission", side_effect=self._permissions),
			patch.object(summary, "validate_report_scope", side_effect=frappe.PermissionError),
			patch.object(summary.frappe, "get_list") as get_list,
		):
			with self.assertRaises(frappe.PermissionError):
				summary.get_bank_exception_summary({"company": "Scope Co"})

		get_list.assert_not_called()

	def test_empty_restricted_scope_cannot_remove_branch_predicate(self):
		with (
			patch.object(summary.frappe, "has_permission", side_effect=self._permissions),
			patch.object(
				summary,
				"validate_report_scope",
				return_value={"restricted": True, "allowed_branches": [], "branch": ""},
			),
		):
			with self.assertRaises(frappe.PermissionError):
				summary._resolve_branch_scope_filter(company="Scope Co", branch="")

	def test_company_or_match_read_denial_precedes_scope_resolution(self):
		for denied in ("Company", "RetailEdge Bank Transaction Match"):
			with self.subTest(denied=denied):
				with (
					patch.object(
						summary.frappe,
						"has_permission",
						side_effect=lambda doctype, *_args, **_kwargs: doctype != denied,
					),
					patch.object(summary, "validate_report_scope") as validate_scope,
				):
					with self.assertRaises(frappe.PermissionError):
						summary._resolve_branch_scope_filter(
							company="Scope Co",
							branch="",
						)

				validate_scope.assert_not_called()

	def test_restricted_multi_scope_is_applied_to_bounded_get_list(self):
		with (
			patch.object(summary.frappe, "has_permission", side_effect=self._permissions),
			patch.object(
				summary,
				"validate_report_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Main", "North"],
					"branch": "",
				},
			),
			patch.object(summary.frappe, "get_list", return_value=[]) as get_list,
		):
			result = summary.get_bank_exception_summary(
				{
					"company": "Scope Co",
					"from_date": "2026-09-01",
					"to_date": "2026-09-05",
				}
			)

		query = get_list.call_args.kwargs
		self.assertEqual(query["filters"]["company"], "Scope Co")
		self.assertEqual(query["filters"]["branch"], ["in", ["Main", "North"]])
		self.assertEqual(query["limit"], summary.MAX_BANK_MATCH_SUMMARY_ROWS + 1)
		self.assertEqual(result["scan"]["rows"], 0)

	def test_summary_remains_read_only_and_candidate_invariant_is_untouched(self):
		source = inspect.getsource(summary)
		self.assertIn("validate_report_scope", source)
		self.assertIn("frappe.get_list", source)
		self.assertNotIn("validate_user_branch_access", source)
		for forbidden in (
			"bank_candidate_engine",
			"find_payment_entry_candidates_for_bank_transaction",
			"find_sales_invoice_candidates_for_bank_transaction",
			"get_direction_aware_bank_candidates",
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
