from __future__ import annotations

import inspect
import unittest
from unittest.mock import call, patch

import frappe

from retailedge import action_center


class TestPrereportingActionCenterScope(unittest.TestCase):
	def test_action_center_uses_assignment_aware_reporting_scope(self):
		source = inspect.getsource(action_center)
		self.assertIn("validate_report_scope", source)
		self.assertNotIn("get_user_allowed_branches", source)
		self.assertNotIn("user_has_global_branch_access", source)
		self.assertNotIn("_validate_operational_scope", source)
		self.assertNotIn("ignore_permissions=True", source)

	def test_stale_restricted_default_resolves_only_one_active_branch(self):
		with patch.object(action_center, "validate_report_scope") as validate_scope:
			validate_scope.side_effect = (
				{
					"restricted": True,
					"allowed_branches": ["Main"],
					"branch": "",
				},
				{
					"restricted": True,
					"allowed_branches": ["Main"],
					"branch": "Main",
				},
			)
			result = action_center._resolve_action_center_default_branch(
				"Scope Co",
				"Stale Branch",
				user="reader@example.com",
			)

		self.assertEqual(result, "Main")
		self.assertEqual(
			validate_scope.call_args_list,
			[
				call(
					company="Scope Co",
					branch="",
					user="reader@example.com",
					require_branch_when_restricted=False,
				),
				call(
					company="Scope Co",
					branch="Main",
					user="reader@example.com",
					require_branch_when_restricted=False,
				),
			],
		)

	def test_ambiguous_restricted_default_is_left_unselected(self):
		with patch.object(
			action_center,
			"validate_report_scope",
			return_value={
				"restricted": True,
				"allowed_branches": ["Main", "North"],
				"branch": "",
			},
		):
			result = action_center._resolve_action_center_default_branch(
				"Scope Co",
				"Stale Branch",
				user="reader@example.com",
			)

		self.assertEqual(result, "")

	def test_valid_default_is_revalidated_before_context_use(self):
		with patch.object(action_center, "validate_report_scope") as validate_scope:
			validate_scope.side_effect = (
				{
					"restricted": True,
					"allowed_branches": ["Main", "North"],
					"branch": "",
				},
				{
					"restricted": True,
					"allowed_branches": ["Main", "North"],
					"branch": "North",
				},
			)
			result = action_center._resolve_action_center_default_branch(
				"Scope Co",
				"North",
				user="reader@example.com",
			)

		self.assertEqual(result, "North")

	def test_unrestricted_blank_branch_preserves_company_wide_scope(self):
		with patch.object(
			action_center,
			"validate_report_scope",
			return_value={"restricted": False, "allowed_branches": [], "branch": ""},
		) as validate_scope:
			result = action_center._resolve_action_center_branch(
				"Scope Co",
				"",
				user="manager@example.com",
			)

		self.assertEqual(result, "")
		validate_scope.assert_called_once_with(
			company="Scope Co",
			branch="",
			user="manager@example.com",
			require_branch_when_restricted=False,
		)

	def test_restricted_zero_scope_denial_precedes_source_composition(self):
		with (
			patch.object(action_center, "validate_report_scope", side_effect=frappe.PermissionError),
			patch.object(action_center, "get_inventory_action_summary") as stock,
		):
			with self.assertRaises(frappe.PermissionError):
				action_center.get_action_center_data({"company": "Scope Co", "branch": ""})

		stock.assert_not_called()

	def test_resolved_scope_is_shared_by_all_composite_sources_and_follow_up_reads(self):
		source = inspect.getsource(action_center.get_action_center_data)
		self.assertLess(source.index("_resolve_action_center_branch"), source.index("_safe_source"))
		for contract in (
			"common = {",
			'"company": company',
			'"branch": branch',
			"get_inventory_action_summary",
			"get_expense_register",
			"get_cash_shift_verification",
			"get_customer_receivables",
			"get_supplier_payables",
			"get_bank_exception_summary(common)",
			"get_customer_sales_action_summary(common)",
			"get_planning_action_summary",
			"decorate_action_items(_dedupe_and_sort(items), company=company, branch=branch)",
		):
			self.assertIn(contract, source)

	def test_scope_slice_remains_read_only(self):
		source = inspect.getsource(action_center)
		for forbidden in (
			"frappe.new_doc(",
			".insert(",
			".submit(",
			"frappe.db.set_value(",
			"frappe.db.commit(",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
