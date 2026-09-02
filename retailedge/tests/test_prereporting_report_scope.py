from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import operating_report_defaults, reporting_actions, stock_accounting_integrity
from retailedge.reporting_scope import (
	assert_company_wide_report_scope,
	get_report_branch_scope,
	validate_report_scope,
)


class RetailEdgePreReportingReportScopeTests(unittest.TestCase):
	def test_branch_assignment_history_uses_operating_context_allowed_branches(self):
		with (
			patch("retailedge.reporting_scope.user_has_global_branch_access", return_value=False),
			patch("retailedge.reporting_scope.has_branch_assignments", return_value=True),
			patch("retailedge.reporting_scope.get_user_allowed_branches", return_value={"branches": []}),
			patch("retailedge.reporting_scope.get_user_branch_profiles", return_value=[]),
			patch(
				"retailedge.reporting_scope.get_allowed_operating_branches",
				return_value=["Lagos", "Ikeja"],
			),
		):
			scope = get_report_branch_scope("PISONMART", user="stock@example.com")

		self.assertTrue(scope["restricted"])
		self.assertEqual(scope["allowed_branches"], ["Lagos", "Ikeja"])
		self.assertEqual(scope["source"], "branch_assignment")

	def test_no_configured_branch_restriction_preserves_legacy_company_wide_access(self):
		with (
			patch("retailedge.reporting_scope.user_has_global_branch_access", return_value=False),
			patch("retailedge.reporting_scope.has_branch_assignments", return_value=False),
			patch("retailedge.reporting_scope.get_user_allowed_branches", return_value={"branches": []}),
			patch("retailedge.reporting_scope.get_user_branch_profiles", return_value=[]),
		):
			scope = get_report_branch_scope("PISONMART", user="legacy@example.com")

		self.assertFalse(scope["restricted"])
		self.assertEqual(scope["source"], "unrestricted_legacy")

	def test_restricted_user_cannot_omit_branch_from_report_scope(self):
		with (
			patch("retailedge.reporting_scope.frappe.has_permission", return_value=True),
			patch(
				"retailedge.reporting_scope.get_report_branch_scope",
				return_value={
					"company": "PISONMART",
					"restricted": True,
					"allowed_branches": ["Lagos"],
					"source": "branch_assignment",
				},
			),
		):
			with self.assertRaises(frappe.PermissionError):
				validate_report_scope(company="PISONMART", branch="", user="stock@example.com")

	def test_explicit_branch_is_revalidated_by_operating_context_authority(self):
		with (
			patch("retailedge.reporting_scope.frappe.has_permission", return_value=True),
			patch(
				"retailedge.reporting_scope.get_report_branch_scope",
				return_value={
					"company": "PISONMART",
					"restricted": True,
					"allowed_branches": ["Lagos"],
					"source": "branch_assignment",
				},
			),
			patch("retailedge.reporting_scope.validate_operating_branch") as validate_branch,
		):
			validated = validate_report_scope(company="PISONMART", branch="Lagos", user="stock@example.com")

		validate_branch.assert_called_once_with(
			company="PISONMART",
			branch="Lagos",
			user="stock@example.com",
			throw=True,
		)
		self.assertEqual(validated["branch"], "Lagos")

	def test_company_wide_control_fails_closed_when_company_branch_universe_is_unknown(self):
		with (
			patch("retailedge.reporting_scope.frappe.has_permission", return_value=True),
			patch("retailedge.reporting_scope.user_has_global_branch_access", return_value=False),
			patch(
				"retailedge.reporting_scope.get_report_branch_scope",
				return_value={
					"company": "PISONMART",
					"restricted": True,
					"allowed_branches": ["Lagos"],
					"source": "branch_assignment",
				},
			),
			patch("retailedge.reporting_scope._configured_company_branches", return_value=[]),
		):
			with self.assertRaises(frappe.PermissionError):
				assert_company_wide_report_scope("PISONMART", user="stock@example.com")

	def test_company_wide_control_allows_restricted_user_only_when_one_proven_branch_matches(self):
		with (
			patch("retailedge.reporting_scope.frappe.has_permission", return_value=True),
			patch("retailedge.reporting_scope.user_has_global_branch_access", return_value=False),
			patch(
				"retailedge.reporting_scope.get_report_branch_scope",
				return_value={
					"company": "PISONMART",
					"restricted": True,
					"allowed_branches": ["Lagos"],
					"source": "branch_assignment",
				},
			),
			patch("retailedge.reporting_scope._configured_company_branches", return_value=["Lagos"]),
		):
			assert_company_wide_report_scope("PISONMART", user="stock@example.com")

	def test_direct_export_constrains_filters_before_capability_and_dataset(self):
		with (
			patch(
				"retailedge.reporting_actions.constrain_report_filters",
				return_value={"company": "PISONMART", "branch": "Lagos"},
			) as constrain,
			patch("retailedge.reporting_actions.require_report_action") as require,
			patch(
				"retailedge.reporting_actions.get_report_dataset",
				return_value={"columns": [], "rows": []},
			) as dataset,
		):
			reporting_actions.get_report_export_data(
				"stock-position",
				{"company": "PISONMART", "branch": "Lagos"},
			)

		constrain.assert_called_once()
		require.assert_called_once_with(
			"stock-position",
			action="export",
			company="PISONMART",
			branch="Lagos",
		)
		dataset.assert_called_once()

	def test_main_screen_and_export_wrappers_share_one_filter_constraint(self):
		source = inspect.getsource(operating_report_defaults)
		for name in (
			"get_sales_by_item",
			"get_sales_by_item_export",
			"get_sales_invoice_register",
			"get_sales_invoice_register_export",
			"get_purchase_register",
			"get_purchase_register_export",
			"get_supplier_payables",
			"get_supplier_payables_export",
			"get_stock_position",
			"get_stock_position_export",
		):
			self.assertIn(f"def {name}", source)
		self.assertIn("constrain_report_filters(", inspect.getsource(operating_report_defaults._constrain_report_filters))
		self.assertNotIn("get_user_branch_profiles", source)

	def test_stock_accounting_company_wide_guard_no_longer_depends_on_branch_company_field(self):
		source = inspect.getsource(stock_accounting_integrity._assert_company_wide_branch_scope)
		self.assertIn("assert_company_wide_report_scope", source)
		self.assertNotIn("Branch", source)
		self.assertNotIn("company", source.replace("company", "", 1))


if __name__ == "__main__":
	unittest.main()
