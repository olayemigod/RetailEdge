from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.bank_account_policy import BRANCH_FIELD, _bank_account_branch_filters
from retailedge.bank_matching_bank_account_cascade import (
	search_bank_matching_bank_accounts,
	validate_bank_matching_bank_account_filter,
)

APP_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = APP_ROOT / "public/js/bank_matching_bank_account_cascade_adapter.js"
PAGE = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"


class BankMatchingBankAccountCascadeTests(unittest.TestCase):
	def test_strict_scope_without_branch_returns_company_wide_filter_only(self):
		with patch("retailedge.bank_account_policy.has_field", return_value=True):
			filters = _bank_account_branch_filters("", strict_branch_scope=True)
		self.assertEqual(filters, [{BRANCH_FIELD: ["in", ["", None]]}])

	def test_strict_scope_with_branch_returns_exact_branch_only(self):
		with patch("retailedge.bank_account_policy.has_field", return_value=True):
			filters = _bank_account_branch_filters("Ketu", strict_branch_scope=True)
		self.assertEqual(filters, [{BRANCH_FIELD: "Ketu"}])

	def test_strict_scope_fails_closed_if_branch_field_is_not_installed(self):
		with patch("retailedge.bank_account_policy.has_field", return_value=False):
			filters = _bank_account_branch_filters("Ketu", strict_branch_scope=True)
		self.assertEqual(filters, [])

	@patch("retailedge.bank_matching_bank_account_cascade.search_retailedge_bank_accounts")
	def test_search_delegates_to_shared_policy_in_strict_mode(self, search_accounts):
		search_accounts.return_value = [{"value": "Access Bank Ketu - Access Bank", "branch": "Ketu"}]
		result = search_bank_matching_bank_accounts(
			company="RetailEdge Consulting",
			branch="Ketu",
			txt="Access",
			limit=20,
		)
		search_accounts.assert_called_once_with(
			company="RetailEdge Consulting",
			branch="Ketu",
			txt="Access",
			limit=20,
			strict_branch_scope=1,
		)
		self.assertEqual(result[0]["branch"], "Ketu")

	@patch("retailedge.bank_matching_bank_account_cascade.resolve_retailedge_bank_account")
	def test_explicit_filter_validation_uses_strict_branch_scope(self, resolve_account):
		resolve_account.return_value = {
			"bank_account": "Access Bank Ketu - Access Bank",
			"branch": "Ketu",
			"scope": "Branch",
		}
		result = validate_bank_matching_bank_account_filter(
			company="RetailEdge Consulting",
			branch="Ketu",
			bank_account="Access Bank Ketu - Access Bank",
		)
		resolve_account.assert_called_once_with(
			company="RetailEdge Consulting",
			branch="Ketu",
			bank_account="Access Bank Ketu - Access Bank",
			strict_branch_scope=True,
		)
		self.assertTrue(result["valid"])
		self.assertEqual(result["scope"], "Branch")

	def test_adapter_preserves_fuzzy_workspace_chain_and_clears_stale_selection(self):
		asset = ADAPTER.read_text()
		for marker in (
			"search_bank_matching_bank_accounts",
			"validate_bank_matching_bank_account_filter",
			"clearMainBankAccountSelection",
			"nextBranch !== lastWorkspaceBranch",
			'requestArgs.bank_account = ""',
			"validateWorkspaceBankAccount(requestArgs)",
			"then(() => originalCall({ ...request, args: requestArgs }))",
		):
			self.assertIn(marker, asset)
		self.assertNotIn("banking_workspace_fuzzy.get_fuzzy_banking_workspace_rows", asset)

	def test_loader_installs_cascade_after_branch_adapter_before_workspace(self):
		page = PAGE.read_text()
		self.assertIn("bank_matching_bank_account_cascade_adapter.js", page)
		boot_start = page.index("function boot(wrapper)")
		markers = (
			"frappe.require(BRANCH_SEARCH_ASSET)",
			"frappe.require(BANK_ACCOUNT_CASCADE_ASSET)",
			"loadBankingStyles()",
			"frappe.require(WORKSPACE_ASSET)",
		)
		positions = [page.index(marker, boot_start) for marker in markers]
		self.assertEqual(positions, sorted(positions))

	def test_adapter_is_valid_javascript(self):
		completed = subprocess.run(
			["node", "--check", str(ADAPTER)],
			capture_output=True,
			text=True,
			check=False,
		)
		self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
	unittest.main()
