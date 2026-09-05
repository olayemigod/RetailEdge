from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import operating_report_defaults, sales_reporting


class TestPrereportingSalesReportingScope(unittest.TestCase):
	def test_sales_family_uses_operational_scope_not_legacy_branch_helpers(self):
		source = inspect.getsource(sales_reporting)
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
				sales_reporting,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch A", "Branch B"],
				},
			),
			patch.object(sales_reporting, "validate_operating_branch"),
		):
			result = sales_reporting._resolve_context_branch(
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
						sales_reporting,
						"get_operational_branch_scope",
						return_value={"restricted": True, "allowed_branches": allowed},
					),
					patch.object(
						sales_reporting,
						"_validate_sales_branch",
						side_effect=frappe.PermissionError,
					),
				):
					result = sales_reporting._resolve_context_branch(
						company="Scope Co",
						candidate="Stale Branch",
						user="reader@example.com",
					)
			self.assertEqual(result, expected)

	def test_unrestricted_context_preserves_valid_legacy_default(self):
		with (
			patch.object(
				sales_reporting,
				"get_operational_branch_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
			patch.object(sales_reporting, "validate_operating_branch"),
		):
			result = sales_reporting._resolve_context_branch(
				company="Scope Co",
				candidate="Default Branch",
				user="reader@example.com",
			)

		self.assertEqual(result, "Default Branch")

	def test_explicit_branch_outside_assignment_scope_is_rejected(self):
		with (
			patch.object(
				sales_reporting,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(sales_reporting.frappe, "throw", side_effect=RuntimeError("denied")),
			patch.object(sales_reporting, "validate_operating_branch") as validate_branch,
		):
			with self.assertRaises(RuntimeError):
				sales_reporting._invoice_branch_scope(frappe._dict(company="Scope Co", branch="Branch B"))

		validate_branch.assert_not_called()

	def test_explicit_authorised_branch_is_revalidated_and_applied(self):
		with (
			patch.object(sales_reporting, "_sales_invoice_branch_field", return_value="branch"),
			patch.object(
				sales_reporting,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(sales_reporting, "validate_operating_branch") as validate_branch,
		):
			result = sales_reporting._invoice_branch_scope(
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
			patch.object(sales_reporting, "_sales_invoice_branch_field", return_value="branch"),
			patch.object(
				sales_reporting,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch B", "Branch A"],
				},
			),
		):
			result = sales_reporting._invoice_branch_scope(frappe._dict(company="Scope Co", branch=""))

		self.assertEqual(result, ("branch", ["in", ["Branch A", "Branch B"]]))

	def test_restricted_zero_branch_blank_read_uses_impossible_predicate(self):
		with (
			patch.object(sales_reporting, "_sales_invoice_branch_field", return_value="branch"),
			patch.object(
				sales_reporting,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": []},
			),
		):
			result = sales_reporting._invoice_branch_scope(frappe._dict(company="Scope Co", branch=""))

		self.assertEqual(result, ("branch", sales_reporting.NO_BRANCH_SCOPE_SENTINEL))

	def test_unrestricted_blank_branch_preserves_company_wide_read(self):
		with (
			patch.object(sales_reporting, "_sales_invoice_branch_field", return_value="branch"),
			patch.object(
				sales_reporting,
				"get_operational_branch_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
		):
			result = sales_reporting._invoice_branch_scope(frappe._dict(company="Scope Co", branch=""))

		self.assertEqual(result, ("branch", None))

	def test_restricted_read_fails_closed_without_invoice_branch_attribution(self):
		with (
			patch.object(sales_reporting, "_sales_invoice_branch_field", return_value=None),
			patch.object(
				sales_reporting,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(sales_reporting.frappe, "throw", side_effect=RuntimeError("unavailable")),
		):
			with self.assertRaises(RuntimeError):
				sales_reporting._invoice_branch_scope(frappe._dict(company="Scope Co", branch=""))

	def test_branch_and_warehouse_options_use_hardened_operational_queries(self):
		source = inspect.getsource(sales_reporting.search_sales_reporting_options)
		self.assertIn("branch_query", source)
		self.assertIn("warehouse_query", source)

	def test_sales_page_export_pairs_share_scoped_dataset_builders(self):
		for endpoint in (
			sales_reporting.get_sales_by_item,
			sales_reporting.get_sales_by_item_export,
		):
			self.assertIn("_build_sales_by_item_dataset", inspect.getsource(endpoint))
		for endpoint in (
			sales_reporting.get_sales_invoice_register,
			sales_reporting.get_sales_invoice_register_export,
		):
			self.assertIn("_build_sales_invoice_register_dataset", inspect.getsource(endpoint))

	def test_items_and_sales_team_reads_follow_permitted_invoice_headers(self):
		for builder in (
			sales_reporting._build_sales_by_item_dataset,
			sales_reporting._build_sales_invoice_register_dataset,
		):
			source = inspect.getsource(builder)
			self.assertIn("_get_permitted_invoice_headers", source)
		item_source = inspect.getsource(sales_reporting._get_invoice_items)
		team_source = inspect.getsource(sales_reporting._salespeople_by_invoice)
		self.assertIn('"parent": ["in", invoice_names]', item_source)
		self.assertIn('"parent": ["in", invoice_names]', team_source)

	def test_governed_wrappers_still_constrain_before_base_dispatch(self):
		for endpoint, base_name, kwargs in (
			(
				operating_report_defaults.get_sales_by_item,
				"_base_get_sales_by_item",
				{"filters": {"company": "Scope Co"}, "page": 1, "page_size": 50},
			),
			(
				operating_report_defaults.get_sales_by_item_export,
				"_base_get_sales_by_item_export",
				{"filters": {"company": "Scope Co"}},
			),
			(
				operating_report_defaults.get_sales_invoice_register,
				"_base_get_sales_invoice_register",
				{"filters": {"company": "Scope Co"}, "page": 1, "page_size": 50},
			),
			(
				operating_report_defaults.get_sales_invoice_register_export,
				"_base_get_sales_invoice_register_export",
				{"filters": {"company": "Scope Co"}},
			),
		):
			with self.subTest(endpoint=endpoint.__name__):
				events = []

				def constrain(filters):
					events.append("constrain")
					return {**filters, "branch": "Branch A"}

				def dispatch(**_kwargs):
					events.append("dispatch")
					return {}

				with (
					patch.object(
						operating_report_defaults,
						"_constrain_report_filters",
						side_effect=constrain,
					),
					patch.object(operating_report_defaults, base_name, side_effect=dispatch),
				):
					endpoint(**kwargs)

				self.assertEqual(events, ["constrain", "dispatch"])


if __name__ == "__main__":
	unittest.main()
