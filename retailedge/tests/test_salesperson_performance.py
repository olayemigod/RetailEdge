# Copyright (c) 2026, ProcessEdge Solutions and contributors
# For license information, please see license.txt

from __future__ import annotations

import json
import os
from collections import Counter
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestSalespersonPerformance(FrappeTestCase):
	def app_path(self, *parts):
		return os.path.join(frappe.get_app_path("retailedge"), *parts)

	def read(self, *parts):
		path = self.app_path(*parts)
		self.assertTrue(os.path.exists(path), f"Missing expected file: {path}")
		with open(path) as handle:
			return handle.read()

	def test_expected_page_files_and_roles_exist(self):
		page_dir = self.app_path("retailedge", "page", "salesperson_performance_dashboard")
		for filename in (
			"salesperson_performance_dashboard.json",
			"salesperson_performance_dashboard.js",
			"salesperson_performance_dashboard.py",
		):
			self.assertTrue(os.path.exists(os.path.join(page_dir, filename)))

		page = json.loads(self.read("retailedge", "page", "salesperson_performance_dashboard", "salesperson_performance_dashboard.json"))
		self.assertEqual(page.get("name"), "salesperson-performance-dashboard")
		self.assertEqual(page.get("module"), "RetailEdge")
		roles = {row.get("role") for row in page.get("roles", [])}
		self.assertTrue({"System Manager", "Accounts Manager", "RetailEdge Manager", "RetailEdge Branch Manager"}.issubset(roles))

	def test_loader_requires_shared_edgeui_before_product_bundle(self):
		content = self.read(
			"retailedge",
			"page",
			"salesperson_performance_dashboard",
			"salesperson_performance_dashboard.js",
		)
		edgeui_index = content.find('requireAsync("edgesuite_ui.bundle.js")')
		product_index = content.find('requireAsync("salesperson_performance.bundle.js")')
		self.assertGreaterEqual(edgeui_index, 0)
		self.assertGreaterEqual(product_index, 0)
		self.assertLess(edgeui_index, product_index)
		self.assertNotIn('await requireAsync("edgeui.bundle.js")', content)
		self.assertNotIn("optional", content)
		self.assertIn("Timed out loading", content)
		self.assertIn("wrapper.appendChild", content)
		self.assertIn("if (!page)", content)
		self.assertIn("[BOOT]", content)

	def test_bundle_uses_product_app_factory_without_mutating_runtime(self):
		content = self.read("public", "js", "salesperson_performance.bundle.js")
		self.assertIn('import { createRetailEdgeApp } from "./retailedge_ui/app_factory"', content)
		self.assertIn("createRetailEdgeApp(SalespersonPerformanceDashboard)", content)
		self.assertIn("unmountSalespersonPerformanceDashboard", content)
		self.assertNotIn('import * as Vue from "vue"', content)
		self.assertNotIn("window.EdgeUI =", content)
		self.assertNotIn("retailedge-local", content)

	def test_vue_uses_shared_components_and_lazy_link_fields(self):
		content = self.read(
			"public",
			"js",
			"salesperson_performance_dashboard",
			"SalespersonPerformanceDashboard.vue",
		)
		for component in (
			"EdgeAppShell",
			"EdgePageLayout",
			"EdgePageHeader",
			"EdgeFilterBar",
			"EdgeBranchContextSwitcher",
			"EdgeLinkField",
			"EdgeStatCard",
			"EdgeStatusBadge",
			"EdgeLoadingState",
			"EdgeErrorState",
			"EdgeEmptyState",
			"EdgeIcon",
		):
			self.assertIn(component, content)
		self.assertGreaterEqual(content.count("<EdgeLinkField"), 3)
		self.assertIn("searchSalespeople", content)
		self.assertIn("searchCustomers", content)
		self.assertIn("searchItems", content)
		self.assertIn("search_salesperson_dashboard_link", content)
		self.assertNotIn("localEdgeUIComponents", content)
		self.assertNotIn("resolveEdgeUIComponents", content)
		self.assertNotIn("const EdgeAppShell", content)
		self.assertNotIn("window.EdgeUI", content)
		self.assertNotIn("coreedge/coreedge/public/js/edgeui", content)
		self.assertNotIn("../../../../../coreedge", content)

	def test_vue_cascades_branch_and_customer_context(self):
		content = self.read(
			"public",
			"js",
			"salesperson_performance_dashboard",
			"SalespersonPerformanceDashboard.vue",
		)
		self.assertIn("onBranchSwitch", content)
		self.assertIn('this.filters.customer = ""', content)
		self.assertIn('this.filters.item = ""', content)
		self.assertIn('fieldname === "customer"', content)
		self.assertIn("All permitted branches", content)
		self.assertIn("company: this.filters.company", content)

	def test_app_factory_requires_link_and_filter_components(self):
		content = self.read("public", "js", "retailedge_ui", "app_factory.js")
		self.assertIn('"EdgeLinkField"', content)
		self.assertIn('"EdgeFilterBar"', content)
		self.assertIn('MINIMUM_EDGE_SUITE_UI_VERSION = "0.6.0"', content)
		self.assertIn("runtime.install(app)", content)

	def test_dashboard_apis_are_whitelisted(self):
		from retailedge.salesperson_performance import (
			get_salesperson_dashboard_options,
			get_salesperson_performance,
			search_salesperson_dashboard_link,
		)

		for method in (get_salesperson_dashboard_options, get_salesperson_performance, search_salesperson_dashboard_link):
			is_whitelisted = getattr(method, "_is_whitelisted", False)
			if not is_whitelisted and hasattr(frappe, "whitelisted"):
				is_whitelisted = method in frappe.whitelisted
			self.assertTrue(is_whitelisted)

	def test_options_api_returns_lazy_search_and_identity_contract(self):
		from retailedge.salesperson_performance import get_salesperson_dashboard_options

		try:
			result = get_salesperson_dashboard_options()
		except frappe.PermissionError:
			return
		for key in (
			"branches",
			"branch_options",
			"salespeople",
			"default_filters",
			"tenant_name",
			"company",
			"branch_name",
			"user_name",
			"identity",
			"lazy_link_search",
		):
			self.assertIn(key, result)
		self.assertTrue(result["lazy_link_search"])
		self.assertEqual(result["salespeople"], [])
		self.assertIn("company", result["default_filters"])

	def test_link_search_rejects_unknown_fields(self):
		from retailedge import salesperson_performance

		with (
			patch.object(salesperson_performance, "assert_can_access_branch_performance"),
			self.assertRaises(frappe.ValidationError),
		):
			salesperson_performance.search_salesperson_dashboard_link("unsupported", "test")

	def test_company_filter_is_applied_to_sales_invoice_query(self):
		from retailedge import salesperson_performance

		summary = {
			"gross_sales": 0,
			"net_sales": 0,
			"total_invoices": 0,
			"total_discount": 0,
			"total_outstanding": 0,
		}
		with (
			patch.object(salesperson_performance, "assert_can_access_branch_performance"),
			patch.object(salesperson_performance, "_validate_dashboard_filters"),
			patch.object(
				salesperson_performance,
				"_resolve_dashboard_branch_access",
				return_value={"global_access": True, "requested_branch": "", "allowed_branches": []},
			),
			patch.object(salesperson_performance, "has_field", return_value=True),
			patch.object(salesperson_performance.frappe.db, "sql", side_effect=[[summary], []]) as sql,
		):
			result = salesperson_performance.get_salesperson_performance(
				{"company": "Retail Company", "from_date": "2026-07-01", "to_date": "2026-07-31"}
			)
		self.assertIn("summary", result)
		first_query, first_params = sql.call_args_list[0].args[:2]
		self.assertIn("si.company = %s", first_query)
		self.assertIn("Retail Company", first_params)

	def test_aggregation_api_structure(self):
		from retailedge.salesperson_performance import get_salesperson_performance

		try:
			result = get_salesperson_performance(
				{"from_date": "2026-07-01", "to_date": "2026-07-06", "limit": 5, "offset": 0}
			)
		except frappe.PermissionError:
			return
		for key in ("summary", "rows", "limit", "offset"):
			self.assertIn(key, result)
		for key in ("gross_sales", "net_sales", "total_invoices", "total_discount", "total_outstanding"):
			self.assertIn(key, result["summary"])

	def test_frontend_does_not_call_candidate_branches_directly(self):
		content = self.read(
			"public",
			"js",
			"salesperson_performance_dashboard",
			"SalespersonPerformanceDashboard.vue",
		)
		self.assertNotIn("retailedge.branch_performance.get_candidate_branches", content)

	def test_dashboard_remains_discoverable_once(self):
		workspace = json.loads(self.read("retailedge", "workspace", "retailedge", "retailedge.json"))
		sidebar = json.loads(self.read("retailedge", "workspace_sidebar", "retailedge", "retailedge.json"))
		for rows in (workspace["links"], sidebar["items"]):
			links = {row["label"]: row for row in rows if row.get("type") == "Link"}
			self.assertEqual(links["Salesperson Performance Dashboard"]["link_type"], "Page")
			self.assertEqual(links["Salesperson Performance Dashboard"]["link_to"], "salesperson-performance-dashboard")
			counts = Counter(
				(row.get("link_type"), row.get("link_to") or row.get("url"))
				for row in rows
				if row.get("type") == "Link"
			)
			self.assertEqual(counts[("Page", "salesperson-performance-dashboard")], 1)

	def test_dashboard_phase_adds_no_business_document_writes(self):
		paths = [
			self.app_path("salesperson_performance.py"),
			self.app_path("public", "js", "salesperson_performance.bundle.js"),
			self.app_path("public", "js", "salesperson_performance_dashboard", "SalespersonPerformanceDashboard.vue"),
		]
		combined = "\n".join(open(path).read().lower() for path in paths)
		for forbidden in ("doc.submit()", "doc.save()", "frappe.client.save", "frappe.client.submit"):
			self.assertNotIn(forbidden, combined)
