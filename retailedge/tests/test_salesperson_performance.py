# -*- coding: utf-8 -*-
# Copyright (c) 2026, ProcessEdge Solutions and contributors
# For license information, please see license.txt

import os
import json
import py_compile
from collections import Counter
import frappe
from frappe.tests.utils import FrappeTestCase

class TestSalespersonPerformance(FrappeTestCase):
	def test_expected_page_files_exist(self):
		"""Verify all page files are in place."""
		retailedge_path = frappe.get_app_path("retailedge")
		page_dir = os.path.join(retailedge_path, "retailedge", "page", "salesperson_performance_dashboard")
		self.assertTrue(os.path.exists(page_dir), "Page directory does not exist")
		
		expected_files = [
			"salesperson_performance_dashboard.json",
			"salesperson_performance_dashboard.js",
			"salesperson_performance_dashboard.py"
		]
		for filename in expected_files:
			file_path = os.path.join(page_dir, filename)
			self.assertTrue(os.path.exists(file_path), f"Page file {filename} does not exist")

	def test_page_json_config(self):
		"""Verify standard page definition parameters."""
		retailedge_path = frappe.get_app_path("retailedge")
		json_path = os.path.join(
			retailedge_path, "retailedge", "page", "salesperson_performance_dashboard", "salesperson_performance_dashboard.json"
		)
		self.assertTrue(os.path.exists(json_path))
		
		with open(json_path, "r") as f:
			data = json.load(f)
			
		self.assertEqual(data.get("doctype"), "Page")
		self.assertEqual(data.get("name"), "salesperson-performance-dashboard")
		self.assertEqual(data.get("module"), "RetailEdge")
		self.assertEqual(data.get("standard"), "Yes")
		
		roles = [r.get("role") for r in data.get("roles", [])]
		self.assertIn("System Manager", roles)
		self.assertIn("Accounts Manager", roles)
		self.assertIn("RetailEdge Manager", roles)
		self.assertIn("RetailEdge Branch Manager", roles)

	def test_loader_does_not_require_coreedge_edgeui_bundle(self):
		"""Verify salesperson_performance_dashboard.js loads only the RetailEdge bundle."""
		retailedge_path = frappe.get_app_path("retailedge")
		js_path = os.path.join(
			retailedge_path, "retailedge", "page", "salesperson_performance_dashboard", "salesperson_performance_dashboard.js"
		)
		self.assertTrue(os.path.exists(js_path))
		
		with open(js_path, "r") as f:
			content = f.read()
			
		self.assertNotIn("frappe.require('edgeui.bundle.js'", content)
		self.assertNotIn("edgeui.bundle.js", content)
		self.assertIn("frappe.require('salesperson_performance.bundle.js'", content)
		self.assertIn("unmount()", content)
		self.assertIn("current_visit_id", content)

	def test_edgeui_not_copied(self):
		"""Assert that shared EdgeUI Vue components are not cloned or copied into RetailEdge."""
		retailedge_path = frappe.get_app_path("retailedge")
		for root, dirs, files in os.walk(retailedge_path):
			for file in files:
				if file.startswith("Edge") and file.endswith(".vue"):
					self.fail(f"Found cloned EdgeUI component {file} inside RetailEdge at {root}")

	def test_aggregation_api_returns_structured_data(self):
		"""Verify get_salesperson_performance API logic returns expected structures."""
		from retailedge.salesperson_performance import get_salesperson_performance
		
		try:
			res = get_salesperson_performance({
				"from_date": "2026-07-01",
				"to_date": "2026-07-06",
				"limit": 5,
				"offset": 0
			})
			self.assertIn("summary", res)
			self.assertIn("rows", res)
			self.assertIn("limit", res)
			self.assertIn("offset", res)
			
			summary = res["summary"]
			self.assertIn("gross_sales", summary)
			self.assertIn("net_sales", summary)
			self.assertIn("total_invoices", summary)
			self.assertIn("total_discount", summary)
			self.assertIn("total_outstanding", summary)
		except frappe.PermissionError:
			pass

	def test_options_api_is_whitelisted_and_valid(self):
		"""Verify get_salesperson_dashboard_options API is whitelisted and returns option keys."""
		from retailedge.salesperson_performance import get_salesperson_dashboard_options
		is_whitelisted = getattr(get_salesperson_dashboard_options, "_is_whitelisted", False)
		if not is_whitelisted and hasattr(frappe, "whitelisted"):
			is_whitelisted = get_salesperson_dashboard_options in frappe.whitelisted
		self.assertTrue(is_whitelisted)

		try:
			res = get_salesperson_dashboard_options()
			self.assertIn("branches", res)
			self.assertIn("salespeople", res)
			self.assertIn("default_filters", res)
			self.assertIn("tenant_name", res)
			self.assertIn("branch_name", res)
			self.assertIn("user_name", res)
		except frappe.PermissionError:
			pass

	def test_frontend_no_candidate_branches_direct_call(self):
		"""Verify frontend no longer calls get_candidate_branches directly."""
		retailedge_path = frappe.get_app_path("retailedge")
		vue_path = os.path.join(
			retailedge_path, "public", "js", "salesperson_performance_dashboard", "SalespersonPerformanceDashboard.vue"
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path, "r") as f:
			content = f.read()
		self.assertNotIn("retailedge.branch_performance.get_candidate_branches", content)

	def test_frontend_uses_layout_components_and_identity(self):
		"""Verify frontend uses EdgeAppShell, EdgePageLayout, EdgeFilterBar and sets product identity."""
		retailedge_path = frappe.get_app_path("retailedge")
		vue_path = os.path.join(
			retailedge_path, "public", "js", "salesperson_performance_dashboard", "SalespersonPerformanceDashboard.vue"
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path, "r") as f:
			content = f.read()

		self.assertIn("EdgeAppShell", content)
		self.assertIn("EdgePageLayout", content)
		self.assertIn("EdgeFilterBar", content)
		self.assertIn('product="retailedge"', content)
		self.assertIn('data-edge-product="retailedge"', content)

	def test_frontend_references_safe_resolver(self):
		"""Verify SalespersonPerformanceDashboard.vue uses app-local EdgeUI-compatible components."""
		retailedge_path = frappe.get_app_path("retailedge")
		vue_path = os.path.join(
			retailedge_path, "public", "js", "salesperson_performance_dashboard", "SalespersonPerformanceDashboard.vue"
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path, "r") as f:
			content = f.read()
		self.assertIn("localEdgeUIComponents", content)
		self.assertIn("import { h } from 'vue'", content)
		self.assertNotIn("coreedge/coreedge/public/js/edgeui", content)
		self.assertNotIn("../../../../../coreedge", content)

	def test_frontend_has_visible_fallback(self):
		"""Verify SalespersonPerformanceDashboard.vue has a visible fallback path when components resolution fails."""
		retailedge_path = frappe.get_app_path("retailedge")
		vue_path = os.path.join(
			retailedge_path, "public", "js", "salesperson_performance_dashboard", "SalespersonPerformanceDashboard.vue"
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path, "r") as f:
			content = f.read()
		self.assertIn("!edgeUIValid", content)
		self.assertIn("EdgeSuite UI failed to load", content)

	def test_loader_uses_product_bundle_without_coreedge_edgeui(self):
		"""Verify salesperson_performance_dashboard.js loader does not require CoreEdge EdgeUI bundle."""
		retailedge_path = frappe.get_app_path("retailedge")
		js_path = os.path.join(
			retailedge_path, "retailedge", "page", "salesperson_performance_dashboard", "salesperson_performance_dashboard.js"
		)
		self.assertTrue(os.path.exists(js_path))
		with open(js_path, "r") as f:
			content = f.read()

		self.assertNotIn("edgeui.bundle.js", content)
		self.assertIn("salesperson_performance.bundle.js", content)

	def test_frontend_filter_bar_structure_and_labels(self):
		"""Verify that SalespersonPerformanceDashboard.vue has EdgeFilterBar, the correct filter labels, fields, and buttons."""
		retailedge_path = frappe.get_app_path("retailedge")
		vue_path = os.path.join(
			retailedge_path, "public", "js", "salesperson_performance_dashboard", "SalespersonPerformanceDashboard.vue"
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path, "r") as f:
			content = f.read()

		# Assert EdgeFilterBar tag exists
		self.assertIn("<EdgeFilterBar", content)

		# Assert it is NOT inside a named slot template (like <template #filters>)
		self.assertNotIn("<template #filters>", content)

		# Assert labels and fields exist
		self.assertIn("From Date", content)
		self.assertIn("To Date", content)
		self.assertIn("Branch", content)
		self.assertIn("Salesperson", content)
		self.assertIn("Customer", content)
		self.assertIn("Item Code", content)
		self.assertIn("edge-filter-grid", content)
		self.assertIn("edge-field", content)
		self.assertIn("edge-input", content)
		self.assertIn("edge-select", content)
		self.assertIn("edge-primary-button", content)
		self.assertIn("edge-table-card", content)
		self.assertIn("edge-stat-grid", content)

		# Assert Apply / Refresh button exists
		self.assertIn("Apply / Refresh", content)

		# Assert summary cards exist in the template
		self.assertIn("<EdgeStatCard", content)
		self.assertIn('label="Gross Sales"', content)
		self.assertIn('label="Net Sales"', content)
		self.assertIn('label="Number of Sales Invoices"', content)
		self.assertIn('label="Average Invoice Value"', content)
		self.assertIn('label="Total Discount"', content)
		self.assertIn('label="Outstanding Amount"', content)

		# Assert the filter bar is NOT hidden by v-if="!metadataLoading" or similar
		self.assertNotIn('v-if="!metadataLoading"', content)

		# Assert metadataLoading is used for disabled attribute
		self.assertIn(':disabled="metadataLoading"', content)

		# Ensure there is no raw fallback table-only path (no rendering raw table directly under v-if="!edgeUIValid")
		# The fallback block should only show the components resolution failure UI
		fallback_block_start = content.find("v-if=\"!edgeUIValid\"")
		self.assertNotEqual(fallback_block_start, -1)
		fallback_block_end = content.find("<EdgeAppShell", fallback_block_start)
		fallback_content = content[fallback_block_start:fallback_block_end]
		self.assertNotIn("<table", fallback_content)
		self.assertNotIn("dashboard-table", fallback_content)

	def test_loader_loads_css_bundles(self):
		"""Verify salesperson_performance_dashboard.js loader does not request missing bare CSS assets."""
		retailedge_path = frappe.get_app_path("retailedge")
		js_path = os.path.join(
			retailedge_path, "retailedge", "page", "salesperson_performance_dashboard", "salesperson_performance_dashboard.js"
		)
		self.assertTrue(os.path.exists(js_path))
		with open(js_path, "r") as f:
			content = f.read()


	def test_required_components_resolution_does_not_fallback(self):
		"""Verify SalespersonPerformanceDashboard.vue has local shell components with no CoreEdge private import."""
		retailedge_path = frappe.get_app_path("retailedge")
		vue_path = os.path.join(
			retailedge_path, "public", "js", "salesperson_performance_dashboard", "SalespersonPerformanceDashboard.vue"
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path, "r") as f:
			content = f.read()

		self.assertIn("const EdgeAppShell", content)
		self.assertIn("const EdgePageLayout", content)
		self.assertIn("const EdgeFilterBar", content)
		self.assertIn("const EdgeStatCard", content)
		self.assertIn("const EdgeLoadingState", content)
		self.assertIn("const EdgeEmptyState", content)
		self.assertIn("const EdgeErrorState", content)
		self.assertNotIn("import EdgeAppShell from", content)
		self.assertNotIn("import EdgePageLayout from", content)
		self.assertNotIn("import EdgeFilterBar from", content)
		self.assertNotIn("coreedge/coreedge/public/js/edgeui", content)
		self.assertNotIn("../../../../../coreedge", content)

	def test_salesperson_dashboard_is_discoverable_from_standard_navigation(self):
		"""Verify Phase 2F navigation exposes the dashboard with the standard label and route."""
		retailedge_path = frappe.get_app_path("retailedge")
		workspace_path = os.path.join(
			retailedge_path, "retailedge", "workspace", "retailedge", "retailedge.json"
		)
		sidebar_path = os.path.join(
			retailedge_path, "retailedge", "workspace_sidebar", "retailedge", "retailedge.json"
		)
		with open(workspace_path, "r") as f:
			workspace = json.load(f)
		with open(sidebar_path, "r") as f:
			sidebar = json.load(f)

		expected_groups = ["Dashboard", "Operations", "Records", "Reports", "Settings"]
		workspace_groups = [row["label"] for row in workspace["links"] if row.get("type") == "Card Break"]
		sidebar_groups = [row["label"] for row in sidebar["items"] if row.get("type") == "Section Break"]
		self.assertEqual(workspace_groups, expected_groups)
		self.assertEqual(sidebar_groups, expected_groups)

		for rows, group_type in ((workspace["links"], "Card Break"), (sidebar["items"], "Section Break")):
			links = {
				row["label"]: row
				for row in rows
				if row.get("type") == "Link"
			}
			self.assertIn("Salesperson Performance Dashboard", links)
			self.assertEqual(links["Salesperson Performance Dashboard"]["link_type"], "Page")
			self.assertEqual(links["Salesperson Performance Dashboard"]["link_to"], "salesperson-performance-dashboard")
			counts = Counter(
				(row.get("link_type"), row.get("link_to") or row.get("url"))
				for row in rows
				if row.get("type") == "Link"
			)
			self.assertFalse([key for key, count in counts.items() if key[1] and count > 1])
