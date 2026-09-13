from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import stock_movement_page


class TestPrereportingStockMovementPageScope(unittest.TestCase):
	def test_page_context_uses_operational_scope_not_legacy_branch_helpers(self):
		source = inspect.getsource(stock_movement_page)
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
				stock_movement_page,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch A", "Branch B"],
				},
			),
			patch.object(stock_movement_page, "validate_operating_branch"),
		):
			result = stock_movement_page._resolve_context_branch(
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
						stock_movement_page,
						"get_operational_branch_scope",
						return_value={"restricted": True, "allowed_branches": allowed},
					),
					patch.object(
						stock_movement_page,
						"_validate_stock_movement_branch",
						side_effect=frappe.PermissionError,
					),
				):
					result = stock_movement_page._resolve_context_branch(
						company="Scope Co",
						candidate="Stale Branch",
						user="reader@example.com",
					)
			self.assertEqual(result, expected)

	def test_unrestricted_context_preserves_valid_legacy_default(self):
		with (
			patch.object(
				stock_movement_page,
				"get_operational_branch_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
			patch.object(stock_movement_page, "validate_operating_branch"),
		):
			result = stock_movement_page._resolve_context_branch(
				company="Scope Co",
				candidate="Default Branch",
				user="reader@example.com",
			)

		self.assertEqual(result, "Default Branch")

	def test_branch_outside_assignment_scope_is_rejected_before_native_validation(self):
		with (
			patch.object(
				stock_movement_page,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(stock_movement_page.frappe, "throw", side_effect=RuntimeError("denied")),
			patch.object(stock_movement_page, "validate_operating_branch") as validate_branch,
		):
			with self.assertRaises(RuntimeError):
				stock_movement_page._validate_stock_movement_branch(
					company="Scope Co",
					branch="Branch B",
					user="reader@example.com",
				)

		validate_branch.assert_not_called()

	def test_authorised_branch_is_revalidated_against_company(self):
		with (
			patch.object(
				stock_movement_page,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(stock_movement_page, "validate_operating_branch") as validate_branch,
		):
			stock_movement_page._validate_stock_movement_branch(
				company="Scope Co",
				branch="Branch A",
				user="reader@example.com",
			)

		validate_branch.assert_called_once_with(
			company="Scope Co",
			branch="Branch A",
			user="reader@example.com",
			throw=True,
		)

	def test_context_resolves_warehouse_only_after_authorised_branch(self):
		def user_default(key):
			return {"Company": "Scope Co", "RetailEdge Branch": "Branch A"}.get(key)

		with (
			patch.object(
				stock_movement_page.frappe.defaults,
				"get_user_default",
				side_effect=user_default,
			),
			patch.object(stock_movement_page.frappe, "has_permission", return_value=True),
			patch.object(stock_movement_page, "_resolve_context_branch", return_value="Branch A"),
			patch.object(
				stock_movement_page,
				"resolve_branch_warehouse_selection",
				return_value={"warehouse": "Branch A Warehouse"},
			) as resolve_warehouse,
			patch.object(stock_movement_page.frappe.db, "get_value", return_value="Reader"),
		):
			context = stock_movement_page.get_stock_movement_page_context()

		self.assertEqual(context["default_filters"]["branch"], "Branch A")
		self.assertEqual(context["default_filters"]["warehouse"], "Branch A Warehouse")
		resolve_warehouse.assert_called_once_with(
			company="Scope Co",
			branch="Branch A",
			warehouse="",
			preference="default",
		)

	def test_restricted_zero_context_does_not_resolve_a_warehouse(self):
		def user_default(key):
			return {"Company": "Scope Co", "RetailEdge Branch": "Stale Branch"}.get(key)

		with (
			patch.object(
				stock_movement_page.frappe.defaults,
				"get_user_default",
				side_effect=user_default,
			),
			patch.object(stock_movement_page.frappe, "has_permission", return_value=True),
			patch.object(stock_movement_page, "_resolve_context_branch", return_value=""),
			patch.object(stock_movement_page, "resolve_branch_warehouse_selection") as resolve_warehouse,
			patch.object(stock_movement_page.frappe.db, "get_value", return_value="Reader"),
		):
			context = stock_movement_page.get_stock_movement_page_context()

		self.assertEqual(context["default_filters"]["branch"], "")
		self.assertEqual(context["default_filters"]["warehouse"], "")
		resolve_warehouse.assert_not_called()

	def test_page_and_export_share_hardened_dataset_authority(self):
		for endpoint in (
			stock_movement_page.get_stock_movement_page,
			stock_movement_page.get_stock_movement_export,
		):
			self.assertIn("_build_stock_movement_dataset", inspect.getsource(endpoint))

	def test_dataset_resolves_warehouse_scope_before_ledger_read(self):
		source = inspect.getsource(stock_movement_page._build_stock_movement_dataset)
		self.assertLess(
			source.index("resolve_warehouse_scope"), source.index("_get_bounded_stock_ledger_rows")
		)

	def test_options_reuse_hardened_branch_and_warehouse_queries(self):
		source = inspect.getsource(stock_movement_page.search_stock_movement_options)
		self.assertIn("branch_query", source)
		self.assertIn("warehouse_query", source)


if __name__ == "__main__":
	unittest.main()
