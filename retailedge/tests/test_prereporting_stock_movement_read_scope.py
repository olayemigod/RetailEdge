from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import stock_movement_filters
from retailedge.retailedge.report.retailedge_stock_movement_history import (
	retailedge_stock_movement_history as report,
)


class TestPrereportingStockMovementReadScope(unittest.TestCase):
	def test_stock_movement_read_boundary_uses_operational_branch_scope(self):
		for module in (report, stock_movement_filters):
			source = inspect.getsource(module)
			self.assertIn("get_operational_branch_scope", source)
			self.assertNotIn("validate_user_branch_access", source)
			self.assertNotIn("get_user_allowed_branches", source)
			self.assertNotIn("user_has_global_branch_access", source)

	def test_report_rejects_explicit_branch_outside_active_assignments(self):
		filters = frappe._dict(
			company="Scope Co",
			branch="Branch B",
			warehouse="Branch B Warehouse",
		)
		with (
			patch.object(
				report,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(report.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				report.resolve_warehouse_scope(filters)

	def test_report_blank_branch_checks_warehouse_against_union_of_assignments(self):
		filters = frappe._dict(company="Scope Co", warehouse="Branch C Warehouse")
		with (
			patch.object(
				report,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch A", "Branch B"],
				},
			),
			patch.object(
				report,
				"get_branch_warehouses",
				side_effect=lambda company, branch: {f"{branch} Warehouse"},
			),
			patch.object(report.frappe.db, "get_value", return_value=("Scope Co", 0)),
			patch.object(report.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				report.resolve_warehouse_scope(filters)

	def test_report_restricted_user_with_zero_active_branches_fails_closed(self):
		filters = frappe._dict(company="Scope Co", warehouse="Warehouse A")
		with (
			patch.object(
				report,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": []},
			),
			patch.object(report.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				report.resolve_warehouse_scope(filters)

	def test_report_unrestricted_user_retains_company_warehouse_behavior(self):
		filters = frappe._dict(company="Scope Co", warehouse="Warehouse A")
		with (
			patch.object(
				report,
				"get_operational_branch_scope",
				return_value={"restricted": False, "allowed_branches": []},
			),
			patch.object(report, "get_branch_warehouses") as branch_warehouses,
			patch.object(report.frappe.db, "get_value", return_value=("Scope Co", 0)),
		):
			self.assertEqual(report.resolve_warehouse_scope(filters), ["Warehouse A"])
		branch_warehouses.assert_not_called()

	def test_branch_search_is_limited_to_active_assignment_branches(self):
		with (
			patch.object(stock_movement_filters, "_assert_company_read"),
			patch.object(stock_movement_filters, "has_field", return_value=True),
			patch.object(
				stock_movement_filters,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(stock_movement_filters.frappe, "get_list", return_value=[["Branch A"]]) as get_list,
		):
			rows = stock_movement_filters.branch_query(
				"Branch", "", "name", 0, 20, {"company": "Scope Co"}
			)

		self.assertEqual(rows, [["Branch A"]])
		query_filters = get_list.call_args.kwargs["filters"]
		self.assertIn(["Branch", "name", "in", ["Branch A"]], query_filters)

	def test_warehouse_search_rejects_explicit_branch_outside_assignments(self):
		with (
			patch.object(stock_movement_filters, "_assert_company_read"),
			patch.object(
				stock_movement_filters,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(stock_movement_filters, "get_first_existing_field", return_value="branch"),
			patch.object(stock_movement_filters.frappe, "throw", side_effect=RuntimeError("denied")),
			patch.object(stock_movement_filters.frappe, "get_list") as get_list,
		):
			with self.assertRaises(RuntimeError):
				stock_movement_filters.warehouse_query(
					"Warehouse",
					"",
					"name",
					0,
					20,
					{"company": "Scope Co", "branch": "Branch B"},
				)
		get_list.assert_not_called()

	def test_restricted_zero_branch_search_returns_no_warehouse_options(self):
		with (
			patch.object(stock_movement_filters, "_assert_company_read"),
			patch.object(
				stock_movement_filters,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": []},
			),
			patch.object(stock_movement_filters, "get_first_existing_field", return_value="branch"),
			patch.object(stock_movement_filters.frappe, "get_list") as get_list,
		):
			rows = stock_movement_filters.warehouse_query(
				"Warehouse", "", "name", 0, 20, {"company": "Scope Co"}
			)

		self.assertEqual(rows, [])
		get_list.assert_not_called()


if __name__ == "__main__":
	unittest.main()
