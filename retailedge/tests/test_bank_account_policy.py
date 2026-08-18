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

	@patch("retailedge.bank_account_policy.validate_user_branch_access")
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
		self.assertEqual(mock_get_list.call_count, 2)
		for call in mock_get_list.call_args_list:
			self.assertLessEqual(call.kwargs["limit_page_length"], 100)

	def test_bank_account_branch_contract_is_migration_safe_and_searchable(self):
		policy = (APP_ROOT / "bank_account_policy.py").read_text(encoding="utf-8")
		custody = (APP_ROOT / "cash_custody.py").read_text(encoding="utf-8")
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
		self.assertIn('doc.paid_to = to_account', custody)
		self.assertIn('validate_cash_deposit_bank_destination(doc)', custody)


if __name__ == "__main__":
	unittest.main()
