from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import cash_shift_verification as page
from retailedge import cash_shift_verification_read_scope as read_scope
from retailedge.daily_sales_audit_read_scope import NO_BRANCH_SCOPE_SENTINEL
from retailedge.retailedge.report.retailedge_cash_shift_verification import (
	retailedge_cash_shift_verification as report,
)


class TestPrereportingCashShiftVerificationReadScope(unittest.TestCase):
	def _resolve(self, branch_scope, *, branch=""):
		with (
			patch.object(read_scope, "assert_cash_shift_verification_read_access"),
			patch.object(read_scope, "_assert_company_read_access"),
			patch.object(
				read_scope,
				"apply_daily_sales_audit_query_branch_scope",
				return_value=branch_scope,
			) as apply_scope,
		):
			result = read_scope.resolve_cash_shift_verification_read_scope(
				{"company": "Scope Co", "branch": branch},
				user="reader@example.com",
			)
		return result, apply_scope

	def test_page_and_report_use_operational_scope_not_legacy_query_scope(self):
		for module in (page, report, read_scope):
			source = inspect.getsource(module)
			self.assertNotIn("get_branch_query_filters", source)
			self.assertNotIn("ignore_permissions=True", source)
			self.assertNotIn("frappe.db.commit()", source)
		self.assertIn("apply_daily_sales_audit_query_branch_scope", inspect.getsource(read_scope))

	def test_restricted_single_branch_blank_read_resolves_exactly(self):
		result, _ = self._resolve({"branch": "Branch A"})
		self.assertEqual(result, {"company": "Scope Co", "branch": "Branch A"})

	def test_restricted_multi_branch_blank_read_uses_union(self):
		result, _ = self._resolve({"branch": ["in", ["Branch A", "Branch B"]]})
		self.assertEqual(result["branch"], ["in", ["Branch A", "Branch B"]])

	def test_restricted_zero_branch_read_uses_impossible_predicate(self):
		result, _ = self._resolve({"branch": NO_BRANCH_SCOPE_SENTINEL})
		self.assertEqual(result["branch"], NO_BRANCH_SCOPE_SENTINEL)

	def test_unrestricted_blank_branch_preserves_company_wide_read(self):
		result, _ = self._resolve({})
		self.assertEqual(result, {"company": "Scope Co"})

	def test_explicit_branch_is_revalidated_by_current_reader(self):
		result, apply_scope = self._resolve({"branch": "Branch A"}, branch="Branch A")
		self.assertEqual(result["branch"], "Branch A")
		apply_scope.assert_called_once_with(
			read_scope.DAILY_SALES_AUDIT_DOCTYPE,
			{"company": "Scope Co", "branch": "Branch A"},
			branch_field="branch",
			user="reader@example.com",
		)

	def test_unauthorised_explicit_branch_failure_is_not_swallowed(self):
		with (
			patch.object(read_scope, "assert_cash_shift_verification_read_access"),
			patch.object(read_scope, "_assert_company_read_access"),
			patch.object(
				read_scope,
				"apply_daily_sales_audit_query_branch_scope",
				side_effect=frappe.PermissionError,
			),
		):
			with self.assertRaises(frappe.PermissionError):
				read_scope.resolve_cash_shift_verification_read_scope(
					{"company": "Scope Co", "branch": "Branch B"},
					user="reader@example.com",
				)

	def test_missing_company_fails_before_audit_query(self):
		with (
			patch.object(read_scope, "assert_cash_shift_verification_read_access") as assert_read,
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("company required")),
			patch.object(read_scope, "apply_daily_sales_audit_query_branch_scope") as apply_scope,
		):
			with self.assertRaises(RuntimeError):
				read_scope.resolve_cash_shift_verification_read_scope({}, user="reader@example.com")

		assert_read.assert_not_called()
		apply_scope.assert_not_called()

	def test_context_fills_only_unambiguous_restricted_branch(self):
		for allowed, expected in (
			(["Branch A"], "Branch A"),
			(["Branch A", "Branch B"], ""),
			([], ""),
		):
			with self.subTest(allowed=allowed):
				with patch.object(
					read_scope,
					"get_daily_sales_audit_branch_scope",
					return_value={"restricted": True, "allowed_branches": allowed},
				):
					result = read_scope.resolve_cash_shift_context_branch(
						company="Scope Co",
						candidate="Stale Branch",
						user="reader@example.com",
					)
				self.assertEqual(result, expected)

	def test_unrestricted_context_preserves_legacy_default(self):
		with patch.object(
			read_scope,
			"get_daily_sales_audit_branch_scope",
			return_value={"restricted": False, "allowed_branches": []},
		):
			result = read_scope.resolve_cash_shift_context_branch(
				company="Scope Co",
				candidate="Default Branch",
				user="reader@example.com",
			)
		self.assertEqual(result, "Default Branch")

	def test_restricted_zero_scope_returns_no_cashier_or_profile_options(self):
		impossible = {"company": "Scope Co", "branch": NO_BRANCH_SCOPE_SENTINEL}
		with patch.object(page.frappe, "get_list") as get_list:
			self.assertEqual(page._search_scoped_cashiers(txt="", read_scope=impossible), [])
			self.assertEqual(
				page._search_scoped_pos_profiles(
					txt="",
					company="Scope Co",
					read_scope=impossible,
				),
				[],
			)
		get_list.assert_not_called()

	def test_cashier_options_are_intersected_with_scoped_audit_rows(self):
		candidates = [
			frappe._dict(name="allowed@example.com", full_name="Allowed Cashier"),
			frappe._dict(name="outside@example.com", full_name="Outside Cashier"),
		]
		with patch.object(
			page.frappe,
			"get_list",
			side_effect=[candidates, [frappe._dict(cashier="allowed@example.com")]],
		) as get_list:
			result = page._search_scoped_cashiers(
				txt="Cashier",
				read_scope={"company": "Scope Co", "branch": ["in", ["Branch A"]]},
			)

		self.assertEqual([row["value"] for row in result], ["allowed@example.com"])
		audit_call = get_list.call_args_list[1]
		self.assertEqual(audit_call.args[0], read_scope.DAILY_SALES_AUDIT_DOCTYPE)
		self.assertEqual(audit_call.kwargs["filters"]["branch"], ["in", ["Branch A"]])

	def test_pos_profile_options_are_intersected_with_scoped_audit_rows(self):
		candidates = [frappe._dict(name="POS A"), frappe._dict(name="POS B")]
		with patch.object(
			page.frappe,
			"get_list",
			side_effect=[candidates, [frappe._dict(pos_profile="POS B")]],
		):
			result = page._search_scoped_pos_profiles(
				txt="POS",
				company="Scope Co",
				read_scope={"company": "Scope Co", "branch": "Branch B"},
			)

		self.assertEqual(result, [{"value": "POS B", "label": "POS B"}])

	def test_option_search_resolves_selected_branch_before_cashier_read(self):
		resolved = {"company": "Scope Co", "branch": "Branch B"}
		with (
			patch.object(
				page, "resolve_cash_shift_verification_read_scope", return_value=resolved
			) as resolve_scope,
			patch.object(page, "_search_scoped_cashiers", return_value=[]) as search_cashiers,
		):
			page.search_cash_shift_verification_options(
				"cashier",
				"Cashier",
				company="Scope Co",
				branch="Branch B",
			)

		resolve_scope.assert_called_once_with(
			{"company": "Scope Co", "branch": "Branch B"},
			user=frappe.session.user,
		)
		search_cashiers.assert_called_once_with(txt="Cashier", read_scope=resolved)

	def test_edgesuite_option_search_sends_current_branch_and_clears_dependants(self):
		component = (
			page.__file__.replace("cash_shift_verification.py", "")
			+ "public/js/cash_shift_verification/CashShiftVerificationReport.vue"
		)
		with open(component, encoding="utf-8") as source_file:
			source = source_file.read()
		self.assertIn("branch: this.filters.branch", source)
		branch_handler = source.split("onBranchSelected(option) {", 1)[1].split("clearBranch()", 1)[0]
		self.assertIn("this.filters.branch = option.value", branch_handler)
		self.assertIn('this.filters.pos_profile = ""', branch_handler)
		self.assertIn('this.filters.cashier = ""', branch_handler)

	def test_page_and_export_share_the_same_bounded_dataset(self):
		for endpoint in (page.get_cash_shift_verification, page.get_cash_shift_verification_export):
			self.assertIn("_build_dataset(_coerce_filters(filters))", inspect.getsource(endpoint))

	def test_child_reads_are_derived_from_scoped_audit_rows(self):
		source = inspect.getsource(report.get_data)
		self.assertIn("get_submitted_deposit_totals", source)
		self.assertIn('[row.get("pos_opening_shift") for row in rows]', source)
		self.assertIn('get_cash_invoice_sync_counts(row.get("name"))', source)


if __name__ == "__main__":
	unittest.main()
