from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import daily_sales_audit_page as page
from retailedge import daily_sales_audit_register_read_scope as read_scope
from retailedge.daily_sales_audit_read_scope import NO_BRANCH_SCOPE_SENTINEL
from retailedge.retailedge.report.retailedge_daily_sales_audit_register import (
	retailedge_daily_sales_audit_register as report,
)


class TestPrereportingDailySalesAuditRegisterScope(unittest.TestCase):
	def _resolve(self, branch_scope, *, branch=""):
		with (
			patch.object(read_scope, "_assert_daily_sales_audit_read_access"),
			patch.object(read_scope, "_assert_company_read_access"),
			patch.object(
				read_scope,
				"apply_daily_sales_audit_query_branch_scope",
				return_value=branch_scope,
			) as apply_scope,
		):
			result = read_scope.resolve_daily_sales_audit_register_read_scope(
				{"company": "Scope Co", "branch": branch},
				user="reader@example.com",
			)
		return result, apply_scope

	def test_report_uses_operational_scope_not_legacy_query_scope(self):
		for module in (report, read_scope):
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
			patch.object(read_scope, "_assert_daily_sales_audit_read_access"),
			patch.object(read_scope, "_assert_company_read_access"),
			patch.object(
				read_scope,
				"apply_daily_sales_audit_query_branch_scope",
				side_effect=frappe.PermissionError,
			),
		):
			with self.assertRaises(frappe.PermissionError):
				read_scope.resolve_daily_sales_audit_register_read_scope(
					{"company": "Scope Co", "branch": "Branch B"},
					user="reader@example.com",
				)

	def test_missing_company_fails_before_audit_query(self):
		with (
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("company required")),
			patch.object(read_scope, "_assert_daily_sales_audit_read_access") as assert_read,
			patch.object(read_scope, "apply_daily_sales_audit_query_branch_scope") as apply_scope,
		):
			with self.assertRaises(RuntimeError):
				read_scope.resolve_daily_sales_audit_register_read_scope({}, user="reader@example.com")

		assert_read.assert_not_called()
		apply_scope.assert_not_called()

	def test_daily_sales_audit_read_permission_is_mandatory(self):
		with (
			patch.object(read_scope.frappe.db, "exists", return_value=True),
			patch.object(read_scope.frappe, "has_permission", return_value=False),
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("read denied")),
		):
			with self.assertRaises(RuntimeError):
				read_scope._assert_daily_sales_audit_read_access()

	def test_selected_company_requires_native_read_permission(self):
		with (
			patch.object(read_scope.frappe.db, "exists", return_value=True),
			patch.object(read_scope.frappe, "has_permission", return_value=False),
			patch.object(read_scope.frappe, "throw", side_effect=RuntimeError("company denied")),
		):
			with self.assertRaises(RuntimeError):
				read_scope._assert_company_read_access("Scope Co")

	def test_business_filters_remain_scalar_dataset_filters(self):
		with (
			patch.object(read_scope, "_assert_daily_sales_audit_read_access"),
			patch.object(read_scope, "_assert_company_read_access"),
			patch.object(read_scope, "apply_daily_sales_audit_query_branch_scope", return_value={}),
		):
			result = read_scope.resolve_daily_sales_audit_register_read_scope(
				{
					"company": "Scope Co",
					"pos_profile": "POS A",
					"cashier": "cashier@example.com",
					"audit_status": "In Review",
					"audit_result": "Shortage",
				},
				user="reader@example.com",
			)
		self.assertEqual(result["pos_profile"], "POS A")
		self.assertEqual(result["cashier"], "cashier@example.com")
		self.assertEqual(result["audit_status"], "In Review")
		self.assertEqual(result["audit_result"], "Shortage")

	def test_non_scalar_company_or_branch_cannot_replace_scope_predicates(self):
		for fieldname in ("company", "branch"):
			with self.subTest(fieldname=fieldname):
				filters = {"company": "Scope Co", fieldname: ["!=", ""]}
				with (
					patch.object(read_scope, "_assert_daily_sales_audit_read_access"),
					patch.object(read_scope, "_assert_company_read_access"),
					patch.object(
						read_scope.frappe,
						"throw",
						side_effect=RuntimeError("single value required"),
					),
				):
					with self.assertRaises(RuntimeError):
						read_scope.resolve_daily_sales_audit_register_read_scope(
							filters,
							user="reader@example.com",
						)

	def test_report_applies_dates_after_authoritative_scope(self):
		with (
			patch.object(
				report,
				"resolve_daily_sales_audit_register_read_scope",
				return_value={"company": "Scope Co", "branch": "Branch A"},
			),
			patch.object(report.frappe, "get_all", return_value=[]) as get_all,
		):
			report.get_data(frappe._dict(company="Scope Co", from_date="2026-09-01", to_date="2026-09-05"))

		query_filters = get_all.call_args.kwargs["filters"]
		self.assertEqual(query_filters["company"], "Scope Co")
		self.assertEqual(query_filters["branch"], "Branch A")
		self.assertEqual(query_filters["audit_date"], ["between", ["2026-09-01", "2026-09-05"]])

	def test_edgesuite_page_and_export_reuse_hardened_register_engine(self):
		self.assertIs(page.get_data, report.get_data)
		for endpoint in (page.get_daily_sales_audit_page, page.get_daily_sales_audit_page_export):
			self.assertIn("_build_dataset(_coerce_filters(filters))", inspect.getsource(endpoint))

	def test_deposit_child_read_is_derived_from_scoped_parent_rows(self):
		source = inspect.getsource(report.get_data)
		self.assertLess(
			source.index("resolve_daily_sales_audit_register_read_scope"),
			source.index("get_submitted_deposit_totals"),
		)
		self.assertIn('[row.get("pos_opening_shift") for row in rows]', source)
		self.assertIn('company=filters.get("company")', source)


if __name__ == "__main__":
	unittest.main()
