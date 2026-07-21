# Copyright (c) 2026, ProcessEdge Solutions and contributors
# For license information, please see license.txt

import os
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestSalespersonPerformanceSecurity(FrappeTestCase):
	@patch("retailedge.salesperson_performance.frappe.db.sql")
	@patch("retailedge.salesperson_performance.assert_can_access_branch_performance")
	@patch("retailedge.salesperson_performance.validate_user_branch_access")
	def test_unauthorised_explicit_branch_is_rejected_before_query(
		self,
		mock_validate_branch,
		mock_assert_page_access,
		mock_sql,
	):
		from retailedge.salesperson_performance import get_salesperson_performance

		mock_validate_branch.side_effect = frappe.PermissionError

		with self.assertRaises(frappe.PermissionError):
			get_salesperson_performance(
				{
					"branch": "Restricted Branch",
					"from_date": "2026-07-01",
					"to_date": "2026-07-21",
				}
			)

		mock_assert_page_access.assert_called_once_with(frappe.session.user)
		mock_validate_branch.assert_called_once_with(
			"Restricted Branch",
			user=frappe.session.user,
			company=None,
			throw=True,
		)
		mock_sql.assert_not_called()

	@patch("retailedge.salesperson_performance.frappe.db.sql")
	@patch("retailedge.salesperson_performance.has_field", return_value=True)
	@patch(
		"retailedge.salesperson_performance.get_branch_query_filters",
		return_value={"branch": "Allowed Branch", "allowed_branches": []},
	)
	@patch("retailedge.salesperson_performance.assert_can_access_branch_performance")
	@patch(
		"retailedge.salesperson_performance.validate_user_branch_access",
		return_value={"allowed": True, "reason": "allowed_branch"},
	)
	def test_authorised_explicit_branch_is_applied_to_queries(
		self,
		mock_validate_branch,
		mock_assert_page_access,
		mock_scope,
		mock_has_field,
		mock_sql,
	):
		from retailedge.salesperson_performance import get_salesperson_performance

		mock_sql.side_effect = [
			[
				frappe._dict(
					gross_sales=0,
					net_sales=0,
					total_invoices=0,
					total_discount=0,
					total_outstanding=0,
				)
			],
			[],
		]

		result = get_salesperson_performance(
			{
				"branch": "Allowed Branch",
				"company": "Retail Company",
				"from_date": "2026-07-01",
				"to_date": "2026-07-21",
				"limit": 5,
				"offset": 0,
			}
		)

		mock_assert_page_access.assert_called_once_with(frappe.session.user)
		mock_validate_branch.assert_called_once_with(
			"Allowed Branch",
			user=frappe.session.user,
			company="Retail Company",
			throw=True,
		)
		mock_scope.assert_called_once_with(
			"Sales Invoice",
			user=frappe.session.user,
			company="Retail Company",
			branch="Allowed Branch",
		)
		self.assertTrue(mock_has_field.called)
		self.assertEqual(mock_sql.call_count, 2)
		self.assertEqual(result["rows"], [])
		self.assertIn("summary", result)
		for call in mock_sql.call_args_list:
			query = call.args[0]
			self.assertIn("si.retailedge_branch = %s", query)
			self.assertIn("Allowed Branch", call.args[1])

	def test_dashboard_runtime_is_optional_and_standalone_safe(self):
		retailedge_path = frappe.get_app_path("retailedge")
		page_path = os.path.join(
			retailedge_path,
			"retailedge",
			"page",
			"salesperson_performance_dashboard",
			"salesperson_performance_dashboard.js",
		)
		bundle_path = os.path.join(
			retailedge_path,
			"public",
			"js",
			"salesperson_performance.bundle.js",
		)

		with open(page_path) as source:
			page_source = source.read()
		with open(bundle_path) as source:
			bundle_source = source.read()

		self.assertIn('requireAsync("edgeui.bundle.js", { optional: true', page_source)
		self.assertIn('requireAsync("salesperson_performance.bundle.js")', page_source)
		self.assertIn("retailedge-local", bundle_source)
		self.assertIn("Vue.createApp", bundle_source)
		self.assertIn("window.EdgeUI = runtime", bundle_source)
		self.assertNotIn("EdgeSuite UI runtime not loaded", bundle_source)
