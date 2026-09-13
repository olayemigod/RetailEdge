from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import customer_receivables

APP_ROOT = Path(__file__).resolve().parents[1]


class TestPrereportingCustomerReceivablesScope(unittest.TestCase):
	def test_receivables_uses_operational_scope_not_legacy_branch_helpers(self):
		source = inspect.getsource(customer_receivables)
		self.assertIn("get_operational_branch_scope", source)
		self.assertIn("validate_operating_branch", source)
		self.assertNotIn("get_user_allowed_branches", source)
		self.assertNotIn("user_has_global_branch_access", source)
		self.assertNotIn("validate_user_branch_access", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_context_preserves_valid_restricted_default(self):
		with (
			patch.object(
				customer_receivables,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch A", "Branch B"],
				},
			),
			patch.object(customer_receivables, "validate_operating_branch"),
		):
			result = customer_receivables._resolve_context_branch(
				company="Scope Co",
				candidate="Branch B",
				user="reader@example.com",
			)

		self.assertEqual(result, "Branch B")

	def test_context_replaces_stale_default_only_when_scope_is_unambiguous(self):
		for allowed, expected in (
			(["Branch A"], "Branch A"),
			(["Branch A", "Branch B"], ""),
			([], ""),
		):
			with self.subTest(allowed=allowed):
				with (
					patch.object(
						customer_receivables,
						"get_operational_branch_scope",
						return_value={"restricted": True, "allowed_branches": allowed},
					),
					patch.object(
						customer_receivables,
						"_validate_receivables_branch",
						side_effect=frappe.PermissionError,
					),
				):
					result = customer_receivables._resolve_context_branch(
						company="Scope Co",
						candidate="Stale Branch",
						user="reader@example.com",
					)
			self.assertEqual(result, expected)

	def test_unrestricted_context_preserves_valid_legacy_default(self):
		with (
			patch.object(
				customer_receivables,
				"get_operational_branch_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
			patch.object(customer_receivables, "validate_operating_branch"),
		):
			result = customer_receivables._resolve_context_branch(
				company="Scope Co",
				candidate="Default Branch",
				user="reader@example.com",
			)

		self.assertEqual(result, "Default Branch")

	def test_explicit_branch_outside_assignment_scope_is_rejected(self):
		with (
			patch.object(customer_receivables, "_sales_invoice_branch_field", return_value="branch"),
			patch.object(
				customer_receivables,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(customer_receivables.frappe, "throw", side_effect=RuntimeError("denied")),
			patch.object(customer_receivables, "validate_operating_branch") as validate_branch,
		):
			with self.assertRaises(RuntimeError):
				customer_receivables._invoice_branch_scope(
					frappe._dict(company="Scope Co", branch="Branch B")
				)

		validate_branch.assert_not_called()

	def test_explicit_authorised_branch_is_revalidated_and_applied(self):
		with (
			patch.object(customer_receivables, "_sales_invoice_branch_field", return_value="branch"),
			patch.object(
				customer_receivables,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(customer_receivables, "validate_operating_branch") as validate_branch,
		):
			result = customer_receivables._invoice_branch_scope(
				frappe._dict(company="Scope Co", branch="Branch A")
			)

		self.assertEqual(result, ("branch", "Branch A"))
		validate_branch.assert_called_once_with(
			company="Scope Co",
			branch="Branch A",
			user=frappe.session.user,
			throw=True,
		)

	def test_restricted_multi_branch_blank_read_uses_allowed_union(self):
		with (
			patch.object(customer_receivables, "_sales_invoice_branch_field", return_value="branch"),
			patch.object(
				customer_receivables,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch B", "Branch A"],
				},
			),
		):
			result = customer_receivables._invoice_branch_scope(frappe._dict(company="Scope Co", branch=""))

		self.assertEqual(result, ("branch", ["in", ["Branch A", "Branch B"]]))

	def test_restricted_zero_branch_blank_read_uses_impossible_predicate(self):
		with (
			patch.object(customer_receivables, "_sales_invoice_branch_field", return_value="branch"),
			patch.object(
				customer_receivables,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": []},
			),
		):
			result = customer_receivables._invoice_branch_scope(frappe._dict(company="Scope Co", branch=""))

		self.assertEqual(result, ("branch", customer_receivables.NO_BRANCH_SCOPE_SENTINEL))

	def test_unrestricted_blank_branch_preserves_company_wide_read(self):
		with (
			patch.object(customer_receivables, "_sales_invoice_branch_field", return_value="branch"),
			patch.object(
				customer_receivables,
				"get_operational_branch_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
		):
			result = customer_receivables._invoice_branch_scope(frappe._dict(company="Scope Co", branch=""))

		self.assertEqual(result, ("branch", None))

	def test_restricted_read_fails_closed_without_invoice_branch_attribution(self):
		with (
			patch.object(customer_receivables, "_sales_invoice_branch_field", return_value=None),
			patch.object(
				customer_receivables,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(customer_receivables.frappe, "throw", side_effect=RuntimeError("unavailable")),
		):
			with self.assertRaises(RuntimeError):
				customer_receivables._invoice_branch_scope(frappe._dict(company="Scope Co", branch=""))

	def test_branch_options_use_hardened_operational_query(self):
		source = inspect.getsource(customer_receivables.search_customer_receivables_options)
		self.assertIn("branch_query", source)

	def test_page_and_export_share_the_scoped_dataset_builder(self):
		for endpoint in (
			customer_receivables.get_customer_receivables,
			customer_receivables.get_customer_receivables_export,
		):
			self.assertIn("_build_customer_receivables_dataset", inspect.getsource(endpoint))

	def test_collections_enrichment_follows_permission_scoped_invoice_headers(self):
		source = inspect.getsource(customer_receivables._build_customer_receivables_dataset)
		self.assertLess(
			source.index("_get_permitted_invoice_headers"), source.index("enrich_receivable_rows")
		)

	def test_read_only_consumers_reuse_the_hardened_receivables_authority(self):
		contracts = {
			"customer_360.py": "_build_customer_receivables_dataset",
			"customer_sales_intelligence.py": "_build_customer_receivables_dataset",
			"cash_flow_outlook.py": "customer_receivables._get_permitted_invoice_headers",
			"liquidity_control.py": "get_customer_receivables_export",
			"planning_intelligence.py": "get_customer_receivables_export",
			"money_dashboard.py": "get_customer_receivables",
			"owner_dashboard.py": "get_customer_receivables",
			"receivables_control.py": "get_customer_receivables_export",
		}
		for filename, contract in contracts.items():
			with self.subTest(filename=filename):
				self.assertIn(contract, (APP_ROOT / filename).read_text())


if __name__ == "__main__":
	unittest.main()
