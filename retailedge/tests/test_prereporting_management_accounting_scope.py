from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import (
	business_control,
	control_early_warning,
	financial_position,
	liquidity_control,
	reporting_scope,
)


class TestPrereportingManagementAccountingScope(unittest.TestCase):
	def test_unrestricted_predicate_validates_company_for_current_reader(self):
		with patch.object(
			reporting_scope,
			"validate_report_scope",
			return_value={"restricted": False, "source": "unrestricted_legacy"},
		) as validate_scope:
			allowed = reporting_scope.has_unrestricted_report_scope(
				"Scope Co",
				user="reader@example.com",
			)

		self.assertTrue(allowed)
		validate_scope.assert_called_once_with(
			company="Scope Co",
			branch="",
			user="reader@example.com",
			require_branch_when_restricted=False,
		)

	def test_restricted_scope_is_not_company_wide(self):
		with patch.object(
			reporting_scope,
			"validate_report_scope",
			return_value={
				"restricted": True,
				"allowed_branches": ["Main"],
				"source": "branch_assignment",
			},
		):
			allowed = reporting_scope.has_unrestricted_report_scope(
				"Scope Co",
				user="reader@example.com",
			)

		self.assertFalse(allowed)

	def test_missing_company_and_scope_errors_fail_closed(self):
		with patch.object(reporting_scope, "validate_report_scope") as validate_scope:
			self.assertFalse(reporting_scope.has_unrestricted_report_scope(""))
			validate_scope.assert_not_called()

		for error in (frappe.PermissionError, frappe.ValidationError):
			with self.subTest(error=error):
				with patch.object(reporting_scope, "validate_report_scope", side_effect=error):
					self.assertFalse(
						reporting_scope.has_unrestricted_report_scope(
							"Scope Co",
							user="reader@example.com",
						)
					)

	def test_all_management_visibility_paths_use_shared_company_scope(self):
		for module in (
			financial_position,
			liquidity_control,
			business_control,
			control_early_warning,
		):
			with self.subTest(module=module.__name__):
				source = inspect.getsource(module)
				self.assertIn("has_unrestricted_report_scope", source)
				self.assertNotIn("user_has_global_branch_access", source)

	def test_financial_position_withholds_company_accounting_for_restricted_reader(self):
		owner = {
			"filters": {"company": "Scope Co", "branch": ""},
			"sections": {
				"receivables": {"available": True, "summary": []},
				"payables": {"available": True, "summary": []},
				"profitability": {
					"available": True,
					"summary": [{"label": "Accounting Net Profit", "value": 900}],
				},
			},
		}
		with (
			patch.object(financial_position, "require_dashboard_action"),
			patch.object(financial_position, "get_owner_dashboard_data", return_value=owner),
			patch.object(financial_position, "has_unrestricted_report_scope", return_value=False),
			patch.object(
				financial_position,
				"_get_liquid_position",
				return_value={"available": False, "accounts": []},
			) as liquid,
		):
			result = financial_position.get_financial_position({"company": "Scope Co"})

		liquid.assert_called_once_with(
			company="Scope Co",
			branch="",
			unrestricted_company_scope=False,
		)
		cards = {row["label"]: row for row in result["selected_period"]}
		self.assertFalse(cards["Accounting Net Profit"]["available"])

	def test_liquidity_passes_company_specific_scope_to_cash_balance(self):
		with (
			patch.object(liquidity_control, "require_dashboard_action"),
			patch.object(liquidity_control, "has_unrestricted_report_scope", return_value=False) as scope,
			patch.object(
				liquidity_control,
				"_get_liquid_position",
				return_value={"available": False, "accounts": [], "reason": "restricted"},
			) as liquid,
			patch.object(liquidity_control, "get_cash_movement", return_value={"summary": []}),
			patch.object(
				liquidity_control,
				"get_customer_receivables_export",
				return_value={"rows": []},
			),
			patch.object(
				liquidity_control,
				"get_supplier_payables_export",
				return_value={"rows": []},
			),
		):
			liquidity_control.get_liquidity_control({"company": "Scope Co"})

		scope.assert_called_once_with("Scope Co", user=frappe.session.user)
		liquid.assert_called_once_with(
			company="Scope Co",
			branch="",
			unrestricted_company_scope=False,
		)

	def test_business_control_hides_accounting_but_preserves_owner_composition(self):
		owner = {
			"filters": {"company": "Scope Co", "branch": ""},
			"sections": {
				"profitability": {
					"available": True,
					"summary": [{"label": "Accounting Net Profit", "value": 900}],
				}
			},
		}
		with (
			patch.object(business_control, "require_dashboard_action"),
			patch.object(business_control, "get_owner_dashboard_data", return_value=owner) as owner_loader,
			patch.object(business_control, "has_unrestricted_report_scope", return_value=False),
		):
			result = business_control.get_business_control_data({"company": "Scope Co"})

		owner_loader.assert_called_once()
		card = next(row for row in result["position"] if row["label"] == "Accounting Net Profit")
		self.assertFalse(card["available"])

	def test_early_warning_does_not_query_company_profit_for_restricted_scope(self):
		filters = frappe._dict(
			company="Scope Co",
			branch="",
			from_date="2026-09-01",
			to_date="2026-09-05",
		)
		with (
			patch.object(control_early_warning, "has_unrestricted_report_scope", return_value=False),
			patch.object(control_early_warning, "get_accounting_profitability") as accounting,
		):
			result = control_early_warning._profitability_trend(filters)

		self.assertFalse(result["available"])
		accounting.assert_not_called()

	def test_branch_filter_short_circuits_company_scope_and_accounting(self):
		filters = frappe._dict(company="Scope Co", branch="Main")
		with (
			patch.object(control_early_warning, "has_unrestricted_report_scope") as scope,
			patch.object(control_early_warning, "get_accounting_profitability") as accounting,
		):
			result = control_early_warning._profitability_trend(filters)

		self.assertFalse(result["available"])
		scope.assert_not_called()
		accounting.assert_not_called()


if __name__ == "__main__":
	unittest.main()
