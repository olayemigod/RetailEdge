from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import banking_readiness as readiness


class TestBankingReadinessReadScope(unittest.TestCase):
	def test_existing_access_gate_still_precedes_inventory_read(self):
		with (
			patch.object(
				readiness,
				"assert_can_access_bank_transaction_matching",
				side_effect=frappe.PermissionError,
			),
			patch.object(readiness, "has_doctype") as has_doctype,
			patch.object(readiness, "_bank_account_rows_for_readiness") as scoped_rows,
		):
			with self.assertRaises(frappe.PermissionError):
				readiness.get_banking_readiness()

		has_doctype.assert_not_called()
		scoped_rows.assert_not_called()

	def test_unauthorized_explicit_company_stops_before_bank_account_query(self):
		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=True),
			patch.object(
				readiness,
				"validate_report_scope",
				side_effect=frappe.PermissionError,
			) as validate_scope,
			patch.object(readiness.frappe, "get_list") as get_list,
		):
			with self.assertRaises(frappe.PermissionError):
				readiness._bank_account_rows_for_readiness("Denied Co")

		validate_scope.assert_called_once_with(
			company="Denied Co",
			branch="",
			user=frappe.session.user,
			require_branch_when_restricted=False,
		)
		get_list.assert_not_called()

	def test_blank_company_is_resolved_by_permission_aware_company_query(self):
		def get_list(doctype, **kwargs):
			if doctype == "Company":
				return ["Allowed Co"]
			if doctype == "Bank Account":
				return [{"name": "Allowed Bank"}]
			raise AssertionError(doctype)

		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=True),
			patch.object(
				readiness,
				"validate_report_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
			patch.object(readiness.frappe, "get_list", side_effect=get_list) as list_rows,
		):
			rows = readiness._bank_account_rows_for_readiness("")

		self.assertEqual(rows, [{"name": "Allowed Bank"}])
		company_query = list_rows.call_args_list[0]
		self.assertEqual(company_query.args, ("Company",))
		self.assertEqual(company_query.kwargs["pluck"], "name")
		bank_query = list_rows.call_args_list[1]
		self.assertEqual(bank_query.args, ("Bank Account",))
		self.assertEqual(bank_query.kwargs["filters"]["company"], "Allowed Co")

	def test_unrestricted_reader_retains_company_wide_inventory(self):
		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=True),
			patch.object(
				readiness,
				"validate_report_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
			patch.object(
				readiness.frappe,
				"get_list",
				return_value=[{"name": "Central Bank"}, {"name": "Branch Bank"}],
			) as get_list,
		):
			rows = readiness._bank_account_rows_for_readiness("Scope Co")

		self.assertEqual([row["name"] for row in rows], ["Branch Bank", "Central Bank"])
		filters = get_list.call_args.kwargs["filters"]
		self.assertEqual(filters["company"], "Scope Co")
		self.assertNotIn("retailedge_branch", filters)

	def test_restricted_reader_queries_only_permitted_branch_accounts(self):
		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=True),
			patch.object(
				readiness,
				"validate_report_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Main", "North", "Main", ""],
				},
			),
			patch.object(
				readiness.frappe,
				"get_list",
				return_value=[{"name": "Main Bank"}, {"name": "North Bank"}],
			) as get_list,
		):
			rows = readiness._bank_account_rows_for_readiness("Scope Co")

		self.assertEqual(len(rows), 2)
		filters = get_list.call_args.kwargs["filters"]
		self.assertEqual(filters["company"], "Scope Co")
		self.assertEqual(filters["retailedge_branch"], ["in", ["Main", "North"]])
		self.assertEqual(
			get_list.call_args.kwargs["limit_page_length"],
			readiness.MAX_BANKING_READINESS_ROWS,
		)

	def test_restricted_zero_scope_fails_closed(self):
		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=True),
			patch.object(
				readiness,
				"validate_report_scope",
				return_value={"restricted": True, "allowed_branches": []},
			),
			patch.object(readiness.frappe, "get_list") as get_list,
		):
			with self.assertRaises(frappe.PermissionError):
				readiness._bank_account_rows_for_readiness("Scope Co")

		get_list.assert_not_called()

	def test_missing_branch_attribution_fails_closed_for_restricted_reader(self):
		def has_field(_doctype, fieldname):
			return fieldname != "retailedge_branch"

		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", side_effect=has_field),
			patch.object(
				readiness,
				"validate_report_scope",
				return_value={"restricted": True, "allowed_branches": ["Main"]},
			),
			patch.object(readiness.frappe, "get_list") as get_list,
		):
			with self.assertRaises(frappe.ValidationError):
				readiness._bank_account_rows_for_readiness("Scope Co")

		get_list.assert_not_called()

	def test_missing_company_attribution_fails_closed(self):
		with (
			patch.object(readiness.frappe, "has_permission", return_value=True),
			patch.object(readiness, "has_field", return_value=False),
			patch.object(readiness, "validate_report_scope") as validate_scope,
			patch.object(readiness.frappe, "get_list") as get_list,
		):
			with self.assertRaises(frappe.ValidationError):
				readiness._bank_account_rows_for_readiness("Scope Co")

		validate_scope.assert_not_called()
		get_list.assert_not_called()

	def test_response_schema_and_summary_remain_compatible(self):
		rows = [{"name": "Ready Bank"}, {"name": "Blocked Bank"}]
		results = {
			"Ready Bank": {"bank_account": "Ready Bank", "readiness": readiness.READINESS_READY},
			"Blocked Bank": {
				"bank_account": "Blocked Bank",
				"readiness": readiness.READINESS_BLOCKED,
			},
		}
		with (
			patch.object(readiness, "assert_can_access_bank_transaction_matching"),
			patch.object(readiness, "has_doctype", return_value=True),
			patch.object(readiness, "_bank_account_rows_for_readiness", return_value=rows),
			patch.object(
				readiness,
				"evaluate_bank_account_readiness",
				side_effect=lambda name, company=None: results[name],
			),
		):
			payload = readiness.get_banking_readiness("Scope Co")

		self.assertEqual(set(payload), {"company", "summary", "rows"})
		self.assertEqual(payload["company"], "Scope Co")
		self.assertEqual(payload["summary"], {"ready": 1, "warning": 0, "blocked": 1})
		self.assertEqual(payload["rows"], [results["Ready Bank"], results["Blocked Bank"]])

	def test_scope_composition_remains_read_only(self):
		source = "\n".join(
			(
				inspect.getsource(readiness._bank_account_rows_for_readiness),
				inspect.getsource(readiness.get_banking_readiness),
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
