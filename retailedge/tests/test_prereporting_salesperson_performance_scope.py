from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import salesperson_performance as performance
from retailedge import salesperson_performance_dashboard as dashboard


class TestPrereportingSalespersonPerformanceReadScope(unittest.TestCase):
	def _resolve(self, scope, *, branch=""):
		with (
			patch.object(performance, "_assert_company_access"),
			patch.object(performance, "get_operational_branch_scope", return_value=scope),
		):
			return performance.resolve_salesperson_performance_read_scope(
				{"company": "Scope Co", "branch": branch},
				user="reader@example.com",
			)

	def _predicate(self, resolved, *, has_branch_field=True):
		with patch.object(
			performance,
			"has_field",
			side_effect=lambda doctype, fieldname: has_branch_field
			and doctype == "Sales Invoice"
			and fieldname == "retailedge_branch",
		):
			return performance._salesperson_invoice_branch_predicate(resolved)

	def test_salesperson_performance_uses_operational_scope_not_legacy_query_scope(self):
		for source in (inspect.getsource(performance), inspect.getsource(dashboard)):
			self.assertIn("resolve_salesperson_performance_read_scope", source)
			self.assertNotIn("get_branch_query_filters", source)
			self.assertNotIn("ignore_permissions=True", source)
			self.assertNotIn("frappe.db.commit()", source)

	def test_missing_company_fails_before_sales_invoice_query(self):
		with (
			patch.object(performance, "_default_company", return_value=""),
			patch.object(performance.frappe, "throw", side_effect=RuntimeError("company required")),
		):
			with self.assertRaises(RuntimeError):
				performance.resolve_salesperson_performance_read_scope({}, user="reader@example.com")

	def test_restricted_single_branch_blank_read_resolves_exactly(self):
		resolved = self._resolve(
			{"restricted": True, "allowed_branches": ["Branch A"], "source": "branch_assignment"}
		)
		self.assertEqual(resolved.get("branch"), "Branch A")
		self.assertEqual(self._predicate(resolved), ("si.`retailedge_branch` = %s", ["Branch A"]))

	def test_restricted_multi_branch_blank_read_uses_assignment_union(self):
		resolved = self._resolve(
			{
				"restricted": True,
				"allowed_branches": ["Branch A", "Branch B"],
				"source": "branch_assignment",
			}
		)
		self.assertEqual(
			self._predicate(resolved),
			("si.`retailedge_branch` IN (%s, %s)", ["Branch A", "Branch B"]),
		)

	def test_restricted_zero_branch_read_uses_impossible_predicate(self):
		resolved = self._resolve({"restricted": True, "allowed_branches": [], "source": "branch_assignment"})
		self.assertEqual(self._predicate(resolved), ("1=0", []))

	def test_restricted_reader_fails_closed_without_invoice_branch_field(self):
		resolved = self._resolve(
			{"restricted": True, "allowed_branches": ["Branch A"], "source": "branch_assignment"}
		)
		self.assertEqual(self._predicate(resolved, has_branch_field=False), ("1=0", []))

	def test_restricted_explicit_branch_outside_assignments_is_rejected(self):
		with (
			patch.object(performance, "_assert_company_access"),
			patch.object(
				performance,
				"get_operational_branch_scope",
				return_value={"restricted": True, "allowed_branches": ["Branch A"]},
			),
			patch.object(performance.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				performance.resolve_salesperson_performance_read_scope(
					{"company": "Scope Co", "branch": "Branch B"},
					user="reader@example.com",
				)

	def test_unrestricted_blank_branch_preserves_company_wide_read(self):
		resolved = self._resolve({"restricted": False, "allowed_branches": [], "source": "global"})
		self.assertEqual(self._predicate(resolved), ("", []))

	def test_branch_options_return_assignment_scope_without_broad_branch_query(self):
		with (
			patch.object(
				performance,
				"resolve_salesperson_performance_read_scope",
				return_value=frappe._dict(
					_branch_scope_restricted=True,
					_allowed_branches=["Branch A", "Branch B"],
				),
			),
			patch.object(performance.frappe, "get_list") as get_list,
		):
			result = performance.get_salesperson_performance_branch_options("Scope Co")

		self.assertEqual(result, ["Branch A", "Branch B"])
		get_list.assert_not_called()

	def test_dashboard_branch_search_returns_no_options_for_restricted_zero_scope(self):
		with patch.object(dashboard, "_search_doctype") as search:
			result = dashboard._search_branches(
				"%%",
				"Scope Co",
				frappe._dict(_branch_scope_restricted=True, _allowed_branches=[]),
			)

		self.assertEqual(result, [])
		search.assert_not_called()

	def test_dashboard_branch_search_uses_assignment_union(self):
		with (
			patch.object(dashboard.frappe, "get_meta") as get_meta,
			patch.object(dashboard, "_search_doctype", return_value=[]) as search,
		):
			get_meta.return_value.has_field.return_value = True
			dashboard._search_branches(
				"%Branch%",
				"Scope Co",
				frappe._dict(
					_branch_scope_restricted=True,
					_allowed_branches=["Branch A", "Branch B"],
				),
			)

		query_filters = search.call_args.kwargs["filters"]
		self.assertIn(["Branch", "name", "in", ["Branch A", "Branch B"]], query_filters)
		self.assertIn(["Branch", "company", "=", "Scope Co"], query_filters)

	def test_non_company_search_validates_company_scope_before_master_read(self):
		with (
			patch.object(dashboard, "assert_can_access_branch_performance"),
			patch.object(
				dashboard,
				"resolve_salesperson_performance_read_scope",
				return_value=frappe._dict(_branch_scope_restricted=False),
			) as resolve_scope,
			patch.object(dashboard, "_search_doctype", return_value=[]) as search,
		):
			dashboard.search_salesperson_dashboard_options("salesperson", "Ada", company="Scope Co")

		resolve_scope.assert_called_once_with({"company": "Scope Co"}, user=frappe.session.user)
		search.assert_called_once()

	def test_aggregate_keeps_submitted_invoice_truth_and_never_mutates_documents(self):
		source = inspect.getsource(performance.get_salesperson_performance)
		self.assertIn('conditions = ["si.docstatus = 1"]', source)
		self.assertIn("_salesperson_invoice_branch_predicate", source)
		self.assertNotIn("save(", source)
		self.assertNotIn("submit(", source)
		self.assertNotIn("cancel(", source)


if __name__ == "__main__":
	unittest.main()
