# Copyright (c) 2026, ProcessEdge Solutions and contributors
# For license information, please see license.txt

import json
import os
import re
from collections import Counter
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestSalespersonPerformance(FrappeTestCase):
	def _read_page_js(self):
		path = os.path.join(
			frappe.get_app_path("retailedge"),
			"retailedge",
			"page",
			"salesperson_performance_dashboard",
			"salesperson_performance_dashboard.js",
		)
		self.assertTrue(os.path.exists(path), "Page JS file does not exist")
		with open(path, encoding="utf-8") as handle:
			return handle.read()

	def _read_vue(self):
		path = os.path.join(
			frappe.get_app_path("retailedge"),
			"public",
			"js",
			"salesperson_performance_dashboard",
			"SalespersonPerformanceDashboard.vue",
		)
		self.assertTrue(os.path.exists(path), "Dashboard Vue file does not exist")
		with open(path, encoding="utf-8") as handle:
			return handle.read()

	def test_expected_page_files_exist(self):
		page_dir = os.path.join(
			frappe.get_app_path("retailedge"),
			"retailedge",
			"page",
			"salesperson_performance_dashboard",
		)
		for filename in (
			"salesperson_performance_dashboard.json",
			"salesperson_performance_dashboard.js",
			"salesperson_performance_dashboard.py",
		):
			self.assertTrue(os.path.exists(os.path.join(page_dir, filename)))

	def test_page_json_config(self):
		path = os.path.join(
			frappe.get_app_path("retailedge"),
			"retailedge",
			"page",
			"salesperson_performance_dashboard",
			"salesperson_performance_dashboard.json",
		)
		with open(path, encoding="utf-8") as handle:
			data = json.load(handle)

		self.assertEqual(data.get("doctype"), "Page")
		self.assertEqual(data.get("name"), "salesperson-performance-dashboard")
		self.assertEqual(data.get("module"), "RetailEdge")
		self.assertEqual(data.get("standard"), "Yes")
		roles = [row.get("role") for row in data.get("roles", [])]
		for role in (
			"System Manager",
			"Accounts Manager",
			"RetailEdge Manager",
			"RetailEdge Branch Manager",
		):
			self.assertIn(role, roles)

	def test_loader_uses_current_edgesuite_runtime_before_product_bundle(self):
		content = self._read_page_js()
		edgeui_match = re.search(r"requireAsync\([\"']edgeui\.bundle\.js[\"']\)", content)
		product_match = re.search(
			r"requireAsync\([\"']salesperson_performance\.bundle\.js[\"']\)", content
		)
		self.assertIsNotNone(edgeui_match)
		self.assertIsNotNone(product_match)
		self.assertLess(edgeui_match.start(), product_match.start())
		self.assertIn("frappe.require(assetName", content)
		self.assertIn("window.EdgeSuiteUI?.components", content)
		self.assertIn("window.mountSalespersonPerformanceDashboard", content)
		self.assertIn("retailedge-dashboard-load-error", content)
		self.assertNotIn("window.EdgeUI", content)
		self.assertNotIn("[BOOT] TRACE", content)

	def test_loader_hides_only_native_page_sidebar_and_expands_content(self):
		content = self._read_page_js()
		for contract in (
			"hideNativePageSidebar",
			'querySelector?.(".layout-side-section")',
			'querySelector?.(".layout-main-section-wrapper")',
			"sideSection.hidden = true",
			'mainWrapper.style.width = "100%"',
			"on_page_show",
		):
			self.assertIn(contract, content)
		# Do not hide the global navbar/product-menu host.
		self.assertNotIn(".navbar", content)
		self.assertNotIn(".desk-navbar", content)

	def test_loader_failure_is_visible_without_edgeui_dependency_cycle(self):
		content = self._read_page_js()
		self.assertIn("renderLoadError", content)
		self.assertIn("wrapper.appendChild(errorDiv)", content)
		self.assertIn("Salesperson Performance Dashboard failed to load", content)
		catch_idx = content.find("} catch (error)")
		self.assertNotEqual(catch_idx, -1)
		catch_block = content[catch_idx : catch_idx + 500]
		self.assertNotIn("frappe.require", catch_block)

	def test_loader_does_not_request_bare_css_assets(self):
		content = self._read_page_js()
		self.assertNotIn("edgeui.bundle.css", content)
		self.assertNotIn("salesperson_performance.bundle.css", content)
		self.assertIn("edgeui.bundle.js", content)
		self.assertIn("salesperson_performance.bundle.js", content)

	def test_edgeui_not_copied(self):
		for root, _dirs, files in os.walk(frappe.get_app_path("retailedge")):
			for filename in files:
				if filename.startswith("Edge") and filename.endswith(".vue"):
					self.fail(f"Found cloned EdgeUI component {filename} inside RetailEdge at {root}")

	def test_aggregation_api_returns_structured_data(self):
		from retailedge.salesperson_performance import get_salesperson_performance

		try:
			res = get_salesperson_performance(
				{"from_date": "2026-07-01", "to_date": "2026-07-06", "limit": 5, "offset": 0}
			)
		except frappe.PermissionError:
			return

		for key in ("summary", "rows", "limit", "offset"):
			self.assertIn(key, res)
		for key in (
			"gross_sales",
			"net_sales",
			"total_invoices",
			"total_discount",
			"total_outstanding",
		):
			self.assertIn(key, res["summary"])

	def test_options_api_is_whitelisted_and_valid(self):
		from retailedge.salesperson_performance import get_salesperson_dashboard_options

		is_whitelisted = getattr(get_salesperson_dashboard_options, "_is_whitelisted", False)
		if not is_whitelisted and hasattr(frappe, "whitelisted"):
			is_whitelisted = get_salesperson_dashboard_options in frappe.whitelisted
		self.assertTrue(is_whitelisted)

		try:
			res = get_salesperson_dashboard_options()
		except frappe.PermissionError:
			return
		for key in (
			"branches",
			"salespeople",
			"default_filters",
			"tenant_name",
			"branch_name",
			"user_name",
		):
			self.assertIn(key, res)

	def test_frontend_no_candidate_branches_direct_call(self):
		content = self._read_vue()
		self.assertNotIn("retailedge.branch_performance.get_candidate_branches", content)

	def test_frontend_uses_edgesuite_layout_and_product_identity(self):
		content = self._read_vue()
		for contract in (
			"EdgeAppShell",
			"EdgePageLayout",
			"EdgeFilterBar",
			'product="retailedge"',
			'data-edge-product="retailedge"',
		):
			self.assertIn(contract, content)

	def test_frontend_uses_build_safe_runtime_resolver(self):
		content = self._read_vue()
		self.assertIn("localEdgeUIComponents", content)
		self.assertIn("resolveEdgeUIComponents", content)
		self.assertRegex(content, r'import\s+\{\s*h\s*\}\s+from\s+["\']vue["\']')
		self.assertNotIn("coreedge/coreedge/public/js/edgeui", content)
		self.assertNotIn("../../../../../coreedge", content)

	def test_frontend_has_visible_fallback(self):
		content = self._read_vue()
		self.assertIn("!edgeUIValid", content)
		self.assertIn("EdgeSuite UI failed to load", content)

	def test_frontend_filter_bar_and_stat_cards_are_business_facing(self):
		content = self._read_vue()
		for label in (
			"From Date",
			"To Date",
			"Branch",
			"Salesperson",
			"Customer",
			"Item Code",
			"Apply / Refresh",
		):
			self.assertIn(label, content)
		for label in (
			'﻿label="Gross Sales"'.lstrip("﻿"),
			'label="Net Sales"',
			'label="Number of Sales Invoices"',
			'label="Average Invoice Value"',
			'label="Total Discount"',
			'label="Outstanding Amount"',
		):
			self.assertIn(label, content)
		self.assertIn("<EdgeFilterBar", content)
		self.assertIn("<EdgeStatCard", content)
		self.assertNotIn("<template #filters>", content)

	def test_frontend_keeps_lightweight_loading_and_fallback_behavior(self):
		content = self._read_vue()
		self.assertNotIn('v-if="!metadataLoading"', content)
		self.assertIn(':disabled="metadataLoading"', content)
		fallback_start = content.find('v-if="!edgeUIValid"')
		self.assertNotEqual(fallback_start, -1)
		fallback_end = content.find("<EdgeAppShell", fallback_start)
		fallback = content[fallback_start:fallback_end]
		self.assertNotIn("<table", fallback)
		self.assertNotIn("dashboard-table", fallback)

	def test_required_components_resolution_has_no_coreedge_private_import(self):
		content = self._read_vue()
		for contract in (
			"const EdgeAppShell",
			"const EdgePageLayout",
			"const EdgeFilterBar",
			"const EdgeStatCard",
			"const EdgeLoadingState",
			"const EdgeEmptyState",
			"const EdgeErrorState",
		):
			self.assertIn(contract, content)
		self.assertNotIn("import EdgeAppShell from", content)
		self.assertNotIn("import EdgePageLayout from", content)
		self.assertNotIn("import EdgeFilterBar from", content)
		self.assertNotIn("coreedge/coreedge/public/js/edgeui", content)

	def test_salesperson_dashboard_is_discoverable_from_standard_navigation(self):
		retailedge_path = frappe.get_app_path("retailedge")
		workspace_path = os.path.join(
			retailedge_path, "retailedge", "workspace", "retailedge", "retailedge.json"
		)
		sidebar_path = os.path.join(
			retailedge_path,
			"retailedge",
			"workspace_sidebar",
			"retailedge",
			"retailedge.json",
		)
		with open(workspace_path, encoding="utf-8") as handle:
			workspace = json.load(handle)
		with open(sidebar_path, encoding="utf-8") as handle:
			sidebar = json.load(handle)

		expected_groups = [
			"Home",
			"Sell",
			"Buy",
			"Stock",
			"Money",
			"Expenses",
			"Customers",
			"Suppliers & Payables",
			"Insights",
			"Review & Approvals",
			"Setup",
		]
		for rows, break_type in (
			(workspace["links"], "Card Break"),
			(sidebar["items"], "Section Break"),
		):
			groups = [row["label"] for row in rows if row.get("type") == break_type]
			self.assertEqual(groups, expected_groups)
			links = {row["label"]: row for row in rows if row.get("type") == "Link"}
			self.assertEqual(links["Salesperson Performance"]["link_type"], "Page")
			self.assertEqual(
				links["Salesperson Performance"]["link_to"],
				"salesperson-performance-dashboard",
			)
			counts = Counter(
				(row.get("link_type"), row.get("link_to") or row.get("url"))
				for row in rows
				if row.get("type") == "Link"
			)
			self.assertFalse([key for key, count in counts.items() if key[1] and count > 1])

	@patch("retailedge.salesperson_performance.frappe.db.sql", return_value=[])
	def test_salesperson_performance_api_date_presets(self, mock_sql):
		from retailedge.salesperson_performance import get_salesperson_performance

		get_salesperson_performance({"date_range_preset": "This Month", "limit": 5, "offset": 0})
		mock_sql.assert_called()
