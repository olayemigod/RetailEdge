from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import branch_performance as performance
from retailedge import branch_performance_dashboard as dashboard


class TestPrereportingBranchPerformanceReadScope(unittest.TestCase):
	def test_branch_performance_uses_operational_scope_not_legacy_query_scope(self):
		performance_source = inspect.getsource(performance)
		dashboard_source = inspect.getsource(dashboard)
		for source in (performance_source, dashboard_source):
			self.assertIn("get_operational_branch_scope", source)
			self.assertNotIn("get_branch_query_filters", source)
			self.assertNotIn("ignore_permissions=True", source)
			self.assertNotIn("frappe.db.commit()", source)

	def test_restricted_multi_branch_scope_is_carried_into_internal_filters(self):
		with patch.object(
			performance,
			"get_operational_branch_scope",
			return_value={
				"restricted": True,
				"allowed_branches": ["Branch A", "Branch B"],
				"source": "branch_assignment",
			},
		):
			result = performance._resolve_branch_scope(
				frappe._dict(company="Scope Co", branch="")
			)

		self.assertTrue(result["restricted"])
		self.assertEqual(result["allowed_branches"], ["Branch A", "Branch B"])
		self.assertFalse(result["filters"].get("branch"))
		self.assertTrue(result["filters"].get("_branch_scope_restricted"))
		self.assertEqual(result["filters"].get("_allowed_branches"), ["Branch A", "Branch B"])

	def test_restricted_single_branch_scope_resolves_blank_read_to_that_branch(self):
		with patch.object(
			performance,
			"get_operational_branch_scope",
			return_value={
				"restricted": True,
				"allowed_branches": ["Branch A"],
				"source": "branch_assignment",
			},
		):
			result = performance._resolve_branch_scope(
				frappe._dict(company="Scope Co", branch="")
			)

		self.assertEqual(result["filters"].get("branch"), "Branch A")

	def test_restricted_explicit_branch_outside_assignments_is_rejected(self):
		with (
			patch.object(
				performance,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch A"],
					"source": "branch_assignment",
				},
			),
			patch.object(performance.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				performance._resolve_branch_scope(
					frappe._dict(company="Scope Co", branch="Branch B")
				)

	def test_restricted_zero_branch_candidate_search_fails_closed(self):
		with (
			patch.object(
				performance,
				"_coerce_filters",
				return_value=frappe._dict(company="Scope Co", branch=""),
			),
			patch.object(
				performance,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": [],
					"source": "branch_assignment",
				},
			),
			patch.object(performance.frappe, "get_all") as get_all,
		):
			self.assertEqual(performance.get_candidate_branches({"company": "Scope Co"}), [])
		get_all.assert_not_called()

	def test_sales_query_uses_in_for_restricted_multi_branch_scope(self):
		filters = frappe._dict(
			_branch_scope_restricted=True,
			_allowed_branches=["Branch A", "Branch B"],
			include_unattributed=1,
		)
		with (
			patch.object(performance, "_sales_invoice_branch_expression", return_value="BRANCH_EXPR"),
			patch.object(
				performance,
				"_sales_invoice_cashier_sql_parts",
				return_value={"join_sql": "", "cashier_expr": "NULL"},
			),
			patch.object(performance, "has_field", return_value=False),
			patch.object(performance, "has_doctype", return_value=False),
		):
			query = performance._sales_invoice_query_parts(filters)

		self.assertIn("BRANCH_EXPR IN (%s, %s)", query["where_sql"])
		self.assertEqual(query["params"], ["Branch A", "Branch B"])

	def test_sales_query_uses_impossible_predicate_for_restricted_zero_scope(self):
		filters = frappe._dict(
			_branch_scope_restricted=True,
			_allowed_branches=[],
			include_unattributed=1,
		)
		with (
			patch.object(performance, "_sales_invoice_branch_expression", return_value="BRANCH_EXPR"),
			patch.object(
				performance,
				"_sales_invoice_cashier_sql_parts",
				return_value={"join_sql": "", "cashier_expr": "NULL"},
			),
			patch.object(performance, "has_field", return_value=False),
			patch.object(performance, "has_doctype", return_value=False),
		):
			query = performance._sales_invoice_query_parts(filters)

		self.assertIn("1=0", query["where_sql"])
		self.assertEqual(query["params"], [])

	def test_non_sales_query_uses_in_for_restricted_multi_branch_scope(self):
		filters = frappe._dict(
			_branch_scope_restricted=True,
			_allowed_branches=["Branch A", "Branch B"],
			include_unattributed=1,
		)
		with (
			patch.object(performance, "_doctype_branch_expression", return_value="BRANCH_EXPR"),
			patch.object(performance, "_first_existing_field", return_value=None),
			patch.object(performance, "has_field", return_value=False),
		):
			where_sql, params = performance._doctype_where_sql("Any DocType", filters)

		self.assertIn("BRANCH_EXPR IN (%s, %s)", where_sql)
		self.assertEqual(params, ["Branch A", "Branch B"])

	def test_fallback_attribution_outside_permitted_branches_is_excluded(self):
		filters = frappe._dict(
			include_fallback_branch_resolution=1,
			include_unattributed=1,
			_branch_scope_restricted=True,
			_allowed_branches=["Branch A"],
		)
		invoice = {
			"name": "SINV-001",
			"company": "Scope Co",
			"pos_profile": None,
			"owner": "cashier@example.com",
			"grand_total": 100.0,
			"net_total": 100.0,
			"outstanding_amount": 0.0,
			"paid_amount": 100.0,
		}
		with (
			patch.object(performance, "_sales_invoice_where_sql", return_value=("1=1", [])),
			patch.object(performance.frappe.db, "sql", return_value=[invoice]),
			patch.object(
				performance,
				"resolve_retailedge_branch_context",
				return_value={"branch": "Branch B"},
			),
			patch.object(performance, "has_field", return_value=False),
		):
			rows = performance._get_unattributed_sales_invoice_rows(filters)

		self.assertEqual(rows, [])

	def test_no_data_diagnostics_use_the_scoped_branch_predicate(self):
		effective = frappe._dict(
			company="Scope Co",
			branch="Branch A",
			from_date="2026-09-01",
			to_date="2026-09-03",
		)
		with (
			patch.object(performance, "_coerce_filters", return_value=effective),
			patch.object(
				performance,
				"_resolve_branch_scope",
				return_value={"filters": effective, "messages": [], "allowed_branches": ["Branch A"]},
			),
			patch.object(performance, "_sales_invoice_where_sql", return_value=("1=0", [])) as sales_where,
			patch.object(performance, "has_doctype", return_value=False),
			patch.object(performance, "_doctype_debug_count", return_value=0),
		):
			performance.get_branch_performance_debug_summary({"company": "Scope Co"})

		self.assertTrue(sales_where.call_args.kwargs["include_branch_filter"])

	def test_dashboard_branch_picker_is_limited_to_assignment_scope(self):
		with (
			patch.object(
				dashboard,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch A", "Branch B"],
				},
			),
			patch.object(dashboard.frappe, "get_meta") as get_meta,
			patch.object(dashboard.frappe, "get_list", return_value=[]) as get_list,
		):
			get_meta.return_value.has_field.return_value = True
			dashboard._search_branches("%Branch%", "Scope Co")

		query_filters = get_list.call_args.kwargs["filters"]
		self.assertIn(["Branch", "name", "in", ["Branch A", "Branch B"]], query_filters)

	def test_dashboard_branch_picker_returns_no_options_for_restricted_zero_scope(self):
		with (
			patch.object(
				dashboard,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": []},
			),
			patch.object(dashboard.frappe, "get_list") as get_list,
		):
			self.assertEqual(dashboard._search_branches("%%", "Scope Co"), [])
		get_list.assert_not_called()


if __name__ == "__main__":
	unittest.main()
