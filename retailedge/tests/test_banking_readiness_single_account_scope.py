from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import banking_readiness as readiness


class TestBankingReadinessSingleAccountScope(unittest.TestCase):
	def test_role_gate_precedes_single_account_scope_check(self):
		with (
			patch.object(
				readiness,
				"assert_can_access_bank_transaction_matching",
				side_effect=frappe.PermissionError,
			),
			patch.object(readiness, "_assert_bank_account_readiness_scope") as scope_guard,
			patch.object(readiness, "evaluate_bank_account_readiness") as evaluate,
		):
			with self.assertRaises(frappe.PermissionError):
				readiness.get_bank_account_readiness("Bank A", company="Scope Co")

		scope_guard.assert_not_called()
		evaluate.assert_not_called()

	def test_explicit_company_is_part_of_permission_aware_bank_account_lookup(self):
		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=True),
			patch.object(readiness.frappe, "get_list", return_value=[]) as get_list,
			patch.object(readiness, "validate_report_scope") as validate_scope,
		):
			with self.assertRaises(frappe.PermissionError):
				readiness._assert_bank_account_readiness_scope("Foreign Bank", company="Denied Co")

		filters = get_list.call_args.kwargs["filters"]
		self.assertEqual(filters, {"name": "Foreign Bank", "company": "Denied Co"})
		validate_scope.assert_not_called()

	def test_blank_company_still_validates_resolved_bank_company(self):
		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=True),
			patch.object(
				readiness.frappe,
				"get_list",
				return_value=[
					{"name": "Foreign Bank", "company": "Foreign Co", "retailedge_branch": "Foreign Branch"}
				],
			),
			patch.object(
				readiness,
				"validate_report_scope",
				side_effect=frappe.PermissionError,
			) as validate_scope,
		):
			with self.assertRaises(frappe.PermissionError):
				readiness._assert_bank_account_readiness_scope("Foreign Bank")

		validate_scope.assert_called_once_with(
			company="Foreign Co",
			branch="",
			user=frappe.session.user,
			require_branch_when_restricted=False,
		)

	def test_unrestricted_reader_may_read_permitted_account(self):
		row = {"name": "Central Bank", "company": "Scope Co", "retailedge_branch": ""}
		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=True),
			patch.object(readiness.frappe, "get_list", return_value=[row]),
			patch.object(
				readiness,
				"validate_report_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
		):
			resolved = readiness._assert_bank_account_readiness_scope("Central Bank", company="Scope Co")

		self.assertEqual(dict(resolved), row)

	def test_restricted_reader_may_read_only_permitted_branch_account(self):
		row = {"name": "Main Bank", "company": "Scope Co", "retailedge_branch": "Main"}
		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=True),
			patch.object(readiness.frappe, "get_list", return_value=[row]),
			patch.object(
				readiness,
				"validate_report_scope",
				return_value={"restricted": True, "allowed_branches": ["Main", "North"]},
			),
		):
			resolved = readiness._assert_bank_account_readiness_scope("Main Bank", company="Scope Co")

		self.assertEqual(resolved.get("retailedge_branch"), "Main")

	def test_restricted_reader_cannot_read_another_branch_account(self):
		row = {"name": "South Bank", "company": "Scope Co", "retailedge_branch": "South"}
		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=True),
			patch.object(readiness.frappe, "get_list", return_value=[row]),
			patch.object(
				readiness,
				"validate_report_scope",
				return_value={"restricted": True, "allowed_branches": ["Main", "North"]},
			),
		):
			with self.assertRaises(frappe.PermissionError):
				readiness._assert_bank_account_readiness_scope("South Bank", company="Scope Co")

	def test_restricted_reader_cannot_use_unassigned_account_as_bypass(self):
		row = {"name": "Central Bank", "company": "Scope Co", "retailedge_branch": ""}
		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=True),
			patch.object(readiness.frappe, "get_list", return_value=[row]),
			patch.object(
				readiness,
				"validate_report_scope",
				return_value={"restricted": True, "allowed_branches": ["Main"]},
			),
		):
			with self.assertRaises(frappe.PermissionError):
				readiness._assert_bank_account_readiness_scope("Central Bank", company="Scope Co")

	def test_endpoint_scopes_before_evaluating_readiness(self):
		payload = {"bank_account": "Main Bank", "readiness": readiness.READINESS_READY}
		with (
			patch.object(readiness, "assert_can_access_bank_transaction_matching"),
			patch.object(
				readiness,
				"_assert_bank_account_readiness_scope",
				return_value={"name": "Main Bank", "company": "Scope Co", "retailedge_branch": "Main"},
			) as scope_guard,
			patch.object(readiness, "evaluate_bank_account_readiness", return_value=payload) as evaluate,
		):
			result = readiness.get_bank_account_readiness("Main Bank", company="Scope Co")

		scope_guard.assert_called_once_with("Main Bank", company="Scope Co")
		evaluate.assert_called_once_with("Main Bank", company="Scope Co")
		self.assertEqual(result, payload)

	def test_single_account_scope_path_remains_read_only(self):
		source = "\n".join(
			(
				inspect.getsource(readiness._assert_bank_account_readiness_scope),
				inspect.getsource(readiness.get_bank_account_readiness),
			)
		)
		self.assertIn("validate_report_scope", source)
		self.assertIn("frappe.get_list", source)
		self.assertNotIn("frappe.get_all", source)
		for forbidden in (
			"ignore_permissions",
			".insert(",
			".save(",
			".submit(",
			"frappe.db.set_value",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
