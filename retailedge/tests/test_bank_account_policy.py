from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.bank_account_policy import (
	BRANCH_FIELD,
	MAX_LINK_RESULTS,
	_bank_account_branch_filters,
	search_retailedge_bank_accounts,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestBankAccountPolicy(unittest.TestCase):
	def test_branch_filter_includes_company_wide_and_current_branch(self):
		with patch("retailedge.bank_account_policy.has_field", return_value=True):
			filters = _bank_account_branch_filters("Aba")

		self.assertEqual(filters[0], {BRANCH_FIELD: ["in", ["", None]]})
		self.assertEqual(filters[1], {BRANCH_FIELD: "Aba"})

	def test_blank_branch_is_the_company_wide_scope(self):
		with patch("retailedge.bank_account_policy.has_field", return_value=True):
			filters = _bank_account_branch_filters("")

		self.assertEqual(filters, [{BRANCH_FIELD: ["in", ["", None]]}])

	@patch("retailedge.bank_account_policy._validate_bank_account_operational_branch", return_value="Aba")
	@patch("retailedge.bank_account_policy._assert_branch_belongs_to_company")
	@patch("retailedge.bank_account_policy.frappe.has_permission", return_value=True)
	@patch("retailedge.bank_account_policy.has_doctype", return_value=True)
	@patch("retailedge.bank_account_policy.has_field", return_value=True)
	@patch("retailedge.bank_account_policy.frappe.get_list")
	def test_search_is_permission_aware_bounded_and_combines_global_with_branch_accounts(
		self,
		mock_get_list,
		_mock_has_field,
		_mock_has_doctype,
		_mock_permission,
		_mock_branch_company,
		_mock_branch_access,
	):
		mock_get_list.side_effect = [
			[
				frappe._dict(
					name="Main Collections - GTBank",
					account="GTBank - DC",
					account_name="Main Collections",
					bank="GTBank",
					bank_account_no="1234567890",
					retailedge_branch="",
				)
			],
			[
				frappe._dict(
					name="Aba Collections - Access Bank",
					account="Access Aba - DC",
					account_name="Aba Collections",
					bank="Access Bank",
					bank_account_no="5555556789",
					retailedge_branch="Aba",
				)
			],
		]

		result = search_retailedge_bank_accounts(
			company="Demo Company",
			branch="Aba",
			txt="",
			limit=20,
		)

		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["scope"], "All Branches")
		self.assertEqual(result[1]["branch"], "Aba")
		self.assertIn("••••7890", result[0]["description"])
		self.assertIn("Aba", result[1]["description"])

		# Assert the search semantics rather than an implementation-specific exact
		# invocation count. Framework wrappers or future bounded probes must not make
		# this compatibility test fail as long as both required scopes are queried
		# safely and permission-aware.
		bank_account_calls = [
			call
			for call in mock_get_list.call_args_list
			if call.args and call.args[0] == "Bank Account"
		]
		queried_filters = [call.kwargs.get("filters", {}) for call in bank_account_calls]
		self.assertTrue(
			any(filters.get(BRANCH_FIELD) == ["in", ["", None]] for filters in queried_filters),
			queried_filters,
		)
		self.assertTrue(
			any(filters.get(BRANCH_FIELD) == "Aba" for filters in queried_filters),
			queried_filters,
		)
		for call in bank_account_calls:
			filters = call.kwargs.get("filters", {})
			self.assertEqual(filters.get("company"), "Demo Company")
			self.assertEqual(filters.get("is_company_account"), 1)
			self.assertEqual(filters.get("disabled"), 0)
			self.assertLessEqual(call.kwargs["limit_page_length"], 100)

	def test_bank_account_branch_contract_is_migration_safe_and_searchable(self):
		policy = (APP_ROOT / "bank_account_policy.py").read_text(encoding="utf-8")
		custody = (APP_ROOT / "cash_custody.py").read_text(encoding="utf-8")
		hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
		client = (APP_ROOT / "public" / "js" / "bank_account.js").read_text(encoding="utf-8")
		self.assertEqual(MAX_LINK_RESULTS, 20)
		self.assertIn('"fieldname": BRANCH_FIELD', policy)
		self.assertIn('"fieldtype": "Link"', policy)
		self.assertIn('"options": "Branch"', policy)
		self.assertIn('"in_standard_filter": 1', policy)
		self.assertIn("search_retailedge_bank_accounts", policy)
		self.assertIn('"bank_account_no": ["like", pattern]', policy)
		self.assertIn('or_filters[BRANCH_FIELD] = ["like", pattern]', policy)
		self.assertIn('"to_bank_account": ""', custody)
		self.assertIn("resolve_retailedge_bank_account", custody)
		self.assertIn("doc.paid_to = to_account", custody)
		self.assertIn("validate_cash_deposit_bank_destination(doc)", custody)
		self.assertIn('"Bank Account": "public/js/bank_account.js"', hooks)
		self.assertIn('"validate": "retailedge.bank_account_policy.validate_bank_account_branch"', hooks)
		self.assertIn('frm.set_query("retailedge_branch"', client)
		self.assertIn('{ company: frm.doc.company }', client)


	def test_cash_deposit_bank_ledger_accepts_select_without_widening_other_workflows(self):
		from retailedge.bank_account_policy import _account_must_be_company_bank_account

		with (
			patch("retailedge.bank_account_policy.frappe.db.exists", return_value=True),
			patch("retailedge.bank_account_policy.frappe.db.get_value", return_value=frappe._dict(
				company="Demo Company", is_group=0, account_type="Bank", disabled=0
			)),
			patch("retailedge.bank_account_policy.has_field", return_value=True),
			patch("retailedge.bank_account_policy.frappe.has_permission",
				side_effect=lambda doctype, ptype, **kwargs: ptype == "select"),
		):
			_account_must_be_company_bank_account("Bank - DC", "Demo Company", allow_account_select=True)
			with self.assertRaises(frappe.PermissionError):
				_account_must_be_company_bank_account("Bank - DC", "Demo Company")

	def test_cash_deposit_bank_ledger_select_does_not_bypass_company_or_account_type(self):
		from retailedge.bank_account_policy import _account_must_be_company_bank_account

		with (
			patch("retailedge.bank_account_policy.frappe.db.exists", return_value=True),
			patch("retailedge.bank_account_policy.has_field", return_value=True),
			patch("retailedge.bank_account_policy.frappe.has_permission", return_value=True),
			patch("retailedge.bank_account_policy.frappe.db.get_value") as get_value,
		):
			for override in (
				{"company": "Other Company"}, {"is_group": 1},
				{"account_type": "Cash"}, {"disabled": 1},
			):
				row = frappe._dict(company="Demo Company", is_group=0, account_type="Bank", disabled=0)
				row.update(override)
				get_value.return_value = row
				with self.assertRaises(frappe.ValidationError):
					_account_must_be_company_bank_account("Bank - DC", "Demo Company", allow_account_select=True)

	def test_cash_deposit_bank_ledger_rejects_no_account_permission(self):
		from retailedge.bank_account_policy import _account_must_be_company_bank_account

		with (
			patch("retailedge.bank_account_policy.frappe.db.exists", return_value=True),
			patch("retailedge.bank_account_policy.frappe.has_permission", return_value=False),
		):
			with self.assertRaises(frappe.PermissionError):
				_account_must_be_company_bank_account("Bank - DC", "Demo Company", allow_account_select=True)


if __name__ == "__main__":
	unittest.main()
