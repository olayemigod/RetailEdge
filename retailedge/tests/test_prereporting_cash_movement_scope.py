from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import cash_movement


class TestPrereportingCashMovementScope(unittest.TestCase):
	def _resolve(self, scope, *, branch=""):
		with patch.object(cash_movement, "get_operational_branch_scope", return_value=scope):
			return cash_movement._resolve_branch_scope(
				company="Scope Co",
				requested_branch=branch,
			)

	def test_cash_movement_uses_operational_scope_not_legacy_branch_helpers(self):
		source = inspect.getsource(cash_movement)
		self.assertIn("get_operational_branch_scope", source)
		self.assertNotIn("get_user_allowed_branches", source)
		self.assertNotIn("user_has_global_branch_access", source)
		self.assertNotIn("validate_user_branch_access", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_restricted_single_branch_blank_read_resolves_exactly(self):
		result = self._resolve(
			{
				"restricted": True,
				"allowed_branches": ["Branch A"],
				"source": "branch_assignment",
			}
		)

		self.assertFalse(result["global_access"])
		self.assertEqual(result["effective_branches"], ["Branch A"])
		self.assertEqual(result["label"], "Branch A")

	def test_restricted_multi_branch_blank_read_uses_allowed_union(self):
		result = self._resolve(
			{
				"restricted": True,
				"allowed_branches": ["Branch B", "Branch A"],
				"source": "branch_assignment",
			}
		)

		self.assertEqual(result["effective_branches"], ["Branch A", "Branch B"])
		self.assertEqual(result["label"], "Permitted branches")

	def test_restricted_zero_branch_scope_fails_closed_in_sql(self):
		branch_scope = self._resolve(
			{
				"restricted": True,
				"allowed_branches": [],
				"source": "branch_assignment",
			}
		)
		where_sql, _values = cash_movement._build_where_sql(
			company="Scope Co",
			from_date=None,
			to_date=None,
			account="",
			movement_type="",
			branch_scope=branch_scope,
			branch_expression="BRANCH_EXPR",
			movement_expression="'Money In'",
		)

		self.assertEqual(branch_scope["effective_branches"], [])
		self.assertIn("1 = 0", where_sql)

	def test_unrestricted_legacy_reader_keeps_company_wide_blank_branch(self):
		result = self._resolve(
			{
				"restricted": False,
				"allowed_branches": [],
				"source": "unrestricted_legacy",
			}
		)

		self.assertTrue(result["global_access"])
		self.assertEqual(result["effective_branches"], [])
		self.assertEqual(result["label"], "Company-wide")

	def test_explicit_branch_outside_assignment_scope_is_rejected(self):
		with (
			patch.object(
				cash_movement,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch A"],
					"source": "branch_assignment",
				},
			),
			patch.object(cash_movement.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				cash_movement._resolve_branch_scope(
					company="Scope Co",
					requested_branch="Branch B",
				)

	def test_context_drops_stale_restricted_default_and_fills_single_assignment(self):
		with (
			patch.object(cash_movement, "_assert_cash_movement_access"),
			patch.object(cash_movement, "_assert_company_read_access"),
			patch.object(cash_movement.frappe.defaults, "get_user_default") as get_default,
			patch.object(
				cash_movement,
				"_resolve_branch_scope",
				return_value={
					"global_access": False,
					"restricted": True,
					"allowed_branches": ["Branch A"],
					"effective_branches": ["Branch A"],
					"label": "Branch A",
					"source": "branch_assignment",
				},
			),
			patch.object(cash_movement.frappe.db, "get_value", return_value="Reader"),
		):
			get_default.side_effect = lambda key: {
				"Company": "Scope Co",
				"RetailEdge Branch": "Stale Branch",
				"Branch": "",
			}.get(key)
			result = cash_movement.get_cash_movement_context()

		self.assertEqual(result["default_filters"]["branch"], "Branch A")

	def test_restricted_zero_branch_search_returns_no_options(self):
		with (
			patch.object(
				cash_movement,
				"_resolve_branch_scope",
				return_value={
					"global_access": False,
					"restricted": True,
					"allowed_branches": [],
					"effective_branches": [],
				},
			),
			patch.object(cash_movement.frappe, "get_list") as get_list,
		):
			self.assertEqual(cash_movement._search_branches(txt="", company="Scope Co"), [])

		get_list.assert_not_called()

	def test_page_and_export_share_the_same_scoped_query_builder(self):
		for endpoint in (cash_movement.get_cash_movement, cash_movement.get_cash_movement_export):
			self.assertIn("_prepare_query", inspect.getsource(endpoint))

	def test_rows_and_summary_share_the_same_authoritative_where_clause(self):
		for query in (cash_movement._query_rows, cash_movement._query_summary):
			source = inspect.getsource(query)
			self.assertIn('query["where_sql"]', source)
			self.assertIn('query["values"]', source)


if __name__ == "__main__":
	unittest.main()
