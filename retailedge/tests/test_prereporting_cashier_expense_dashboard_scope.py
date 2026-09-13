from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from retailedge import cashier_expense_dashboard as dashboard


class TestPrereportingCashierExpenseDashboardScope(unittest.TestCase):
	def test_dashboard_uses_operational_scope_not_legacy_query_scope(self):
		source = inspect.getsource(dashboard)
		self.assertIn("get_operational_branch_scope", source)
		self.assertNotIn("get_branch_query_filters", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_restricted_explicit_branch_outside_assignments_is_rejected(self):
		with (
			patch.object(
				dashboard,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch A"],
					"source": "branch_assignment",
				},
			),
			patch.object(dashboard.frappe, "throw", side_effect=RuntimeError("denied")),
		):
			with self.assertRaises(RuntimeError):
				dashboard._build_dashboard_filters(
					{"company": "Scope Co", "branch": "Branch B"}
				)

	def test_restricted_single_branch_blank_filter_resolves_to_that_branch(self):
		with patch.object(
			dashboard,
			"get_operational_branch_scope",
			return_value={
				"restricted": True,
				"allowed_branches": ["Branch A"],
				"source": "branch_assignment",
			},
		):
			filters = dashboard._build_dashboard_filters({"company": "Scope Co"})

		self.assertEqual(filters["company"], "Scope Co")
		self.assertEqual(filters["branch"], "Branch A")

	def test_restricted_multi_branch_blank_filter_uses_only_permitted_branches(self):
		with patch.object(
			dashboard,
			"get_operational_branch_scope",
			return_value={
				"restricted": True,
				"allowed_branches": ["Branch A", "Branch B"],
				"source": "branch_assignment",
			},
		):
			filters = dashboard._build_dashboard_filters({"company": "Scope Co"})

		self.assertEqual(filters["branch"], ["in", ["Branch A", "Branch B"]])

	def test_restricted_zero_branch_scope_fails_closed(self):
		with patch.object(
			dashboard,
			"get_operational_branch_scope",
			return_value={
				"restricted": True,
				"allowed_branches": [],
				"source": "branch_assignment",
			},
		):
			filters = dashboard._build_dashboard_filters({"company": "Scope Co"})

		self.assertEqual(filters["branch"], dashboard.NO_BRANCH_SCOPE_SENTINEL)

	def test_unrestricted_blank_branch_preserves_company_wide_read(self):
		with patch.object(
			dashboard,
			"get_operational_branch_scope",
			return_value={
				"restricted": False,
				"allowed_branches": [],
				"source": "global",
			},
		):
			filters = dashboard._build_dashboard_filters({"company": "Scope Co"})

		self.assertEqual(filters["company"], "Scope Co")
		self.assertNotIn("branch", filters)

	def test_company_defaults_when_filter_is_blank(self):
		with (
			patch.object(
				dashboard.frappe.defaults,
				"get_user_default",
				return_value="Scope Co",
			),
			patch.object(
				dashboard,
				"get_operational_branch_scope",
				return_value={
					"restricted": True,
					"allowed_branches": ["Branch A"],
					"source": "branch_assignment",
				},
			),
		):
			filters = dashboard._build_dashboard_filters({})

		self.assertEqual(filters["company"], "Scope Co")
		self.assertEqual(filters["branch"], "Branch A")

	def test_existing_non_branch_filters_are_preserved(self):
		with patch.object(
			dashboard,
			"get_operational_branch_scope",
			return_value={
				"restricted": False,
				"allowed_branches": [],
				"source": "global",
			},
		):
			filters = dashboard._build_dashboard_filters(
				{
					"company": "Scope Co",
					"pos_profile": "POS-1",
					"cashier": "cashier@example.com",
					"from_date": "2026-09-01",
					"to_date": "2026-09-03",
				}
			)

		self.assertEqual(filters["pos_profile"], "POS-1")
		self.assertEqual(filters["cashier"], "cashier@example.com")
		self.assertEqual(
			filters["expense_date"],
			["between", ["2026-09-01", "2026-09-03"]],
		)


if __name__ == "__main__":
	unittest.main()
