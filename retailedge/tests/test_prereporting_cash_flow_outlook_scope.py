from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import cash_flow_outlook


class TestPrereportingCashFlowOutlookScope(unittest.TestCase):
	def test_outlook_uses_operational_scope_not_legacy_branch_helpers(self):
		source = inspect.getsource(cash_flow_outlook)
		self.assertIn("get_operational_branch_scope", source)
		self.assertIn("validate_operating_branch", source)
		self.assertNotIn("get_user_allowed_branches", source)
		self.assertNotIn("user_has_global_branch_access", source)
		self.assertNotIn("validate_user_branch_access", source)
		self.assertNotIn("ignore_permissions=True", source)

	def test_default_preserves_valid_restricted_branch(self):
		with (
			patch.object(cash_flow_outlook.frappe, "has_permission", return_value=True),
			patch.object(
				cash_flow_outlook.frappe.defaults,
				"get_user_default",
				return_value="Branch B",
			),
			patch.object(
				cash_flow_outlook,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch A", "Branch B"],
				},
			),
			patch.object(cash_flow_outlook, "validate_operating_branch"),
		):
			result = cash_flow_outlook._default_branch("Scope Co")

		self.assertEqual(result, "Branch B")

	def test_stale_default_resolves_only_one_unambiguous_branch(self):
		for allowed, expected in (
			(["Branch A"], "Branch A"),
			(["Branch A", "Branch B"], ""),
			([], ""),
		):
			with self.subTest(allowed=allowed):
				with (
					patch.object(cash_flow_outlook.frappe, "has_permission", return_value=True),
					patch.object(
						cash_flow_outlook.frappe.defaults,
						"get_user_default",
						return_value="Stale Branch",
					),
					patch.object(
						cash_flow_outlook,
						"get_operational_branch_scope",
						return_value={"restricted": True, "allowed_branches": allowed},
					),
					patch.object(
						cash_flow_outlook,
						"_validate_outlook_branch",
						side_effect=frappe.PermissionError,
					),
				):
					result = cash_flow_outlook._default_branch("Scope Co")
			self.assertEqual(result, expected)

	def test_unrestricted_reader_preserves_valid_legacy_default(self):
		with (
			patch.object(cash_flow_outlook.frappe, "has_permission", return_value=True),
			patch.object(
				cash_flow_outlook.frappe.defaults,
				"get_user_default",
				return_value="Default Branch",
			),
			patch.object(
				cash_flow_outlook,
				"get_operational_branch_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
			patch.object(cash_flow_outlook, "validate_operating_branch"),
		):
			result = cash_flow_outlook._default_branch("Scope Co")

		self.assertEqual(result, "Default Branch")

	def test_explicit_branch_outside_assignment_scope_is_rejected(self):
		with (
			patch.object(
				cash_flow_outlook,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(cash_flow_outlook.frappe, "throw", side_effect=RuntimeError("denied")),
			patch.object(cash_flow_outlook, "validate_operating_branch") as validate_branch,
		):
			with self.assertRaises(RuntimeError):
				cash_flow_outlook._validate_outlook_branch(
					company="Scope Co",
					branch="Branch B",
					user="reader@example.com",
				)

		validate_branch.assert_not_called()

	def test_explicit_authorised_branch_is_revalidated(self):
		with (
			patch.object(
				cash_flow_outlook,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(cash_flow_outlook, "validate_operating_branch") as validate_branch,
		):
			cash_flow_outlook._validate_outlook_branch(
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

	def test_branch_options_use_hardened_operational_query(self):
		source = inspect.getsource(cash_flow_outlook.search_cash_flow_outlook_options)
		self.assertIn("branch_query", source)

	def test_permitted_invoice_intersection_precedes_native_schedule_reads(self):
		source = inspect.getsource(cash_flow_outlook._build_dataset)
		self.assertLess(source.index("_validate_outlook_branch"), source.index("require_report_action"))
		self.assertLess(source.index("_permitted_invoice_names"), source.index("_native_outstanding_rows"))

	def test_permitted_names_reuse_hardened_sales_and_purchase_authorities(self):
		source = inspect.getsource(cash_flow_outlook._permitted_invoice_names)
		for contract in (
			"customer_receivables._assert_report_access",
			"customer_receivables._get_permitted_invoice_headers",
			"purchase_reporting._assert_report_access",
			"purchase_reporting._get_permitted_invoice_headers",
		):
			self.assertIn(contract, source)

	def test_native_rows_are_limited_to_permitted_invoice_names(self):
		rows = [
			frappe._dict(voucher_type="Sales Invoice", voucher_no="SINV-1", outstanding=100),
			frappe._dict(voucher_type="Sales Invoice", voucher_no="SINV-2", outstanding=200),
			frappe._dict(voucher_type="Purchase Invoice", voucher_no="SINV-1", outstanding=300),
			frappe._dict(voucher_type="Sales Invoice", voucher_no="SINV-3", outstanding=0),
		]

		result = cash_flow_outlook._eligible_native_rows(
			rows,
			voucher_type="Sales Invoice",
			permitted_names={"SINV-1", "SINV-3"},
		)

		self.assertEqual([row.voucher_no for row in result], ["SINV-1"])

	def test_screen_and_export_share_one_dataset_authority(self):
		self.assertIn("_build_dataset", inspect.getsource(cash_flow_outlook.get_cash_flow_outlook))
		self.assertIn(
			"get_cash_flow_outlook", inspect.getsource(cash_flow_outlook.get_cash_flow_outlook_export)
		)

	def test_outlook_remains_read_only_and_not_forecasting(self):
		source = inspect.getsource(cash_flow_outlook)
		for forbidden in (
			"frappe.new_doc(",
			".insert(",
			".submit(",
			"frappe.db.set_value(",
			"frappe.db.commit(",
			"build_baseline_forecast",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
