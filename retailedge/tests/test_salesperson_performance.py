# Copyright (c) 2026, ProcessEdge Solutions and contributors
# For license information, please see license.txt

import json
import os
import py_compile
import re
from collections import Counter
from unittest.mock import patch

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
			"salesperson_performance_dashboard.py",
		]
		for filename in expected_files:
			file_path = os.path.join(page_dir, filename)
			self.assertTrue(os.path.exists(file_path), f"Page file {filename} does not exist")

	def test_page_json_config(self):
		"""Verify standard page definition parameters."""
		retailedge_path = frappe.get_app_path("retailedge")
		json_path = os.path.join(
			retailedge_path,
			"retailedge",
			"page",
			"salesperson_performance_dashboard",
			"salesperson_performance_dashboard.json",
		)
		self.assertTrue(os.path.exists(json_path))

		with open(json_path) as f:
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

	def test_loader_loads_edgeui_before_product_bundle(self):
		"""Verify salesperson_performance_dashboard.js loads public EdgeUI before the RetailEdge bundle."""
		retailedge_path = frappe.get_app_path("retailedge")
		js_path = os.path.join(
			retailedge_path,
			"retailedge",
			"page",
			"salesperson_performance_dashboard",
			"salesperson_performance_dashboard.js",
		)
		self.assertTrue(os.path.exists(js_path))

		with open(js_path) as f:
			content = f.read()

		edgeui_match = re.search(r"requireAsync\([\"']edgeui\.bundle\.js[\"']\)", content)
		product_match = re.search(r"requireAsync\([\"']salesperson_performance\.bundle\.js[\"']\)", content)
		edgeui_idx = edgeui_match.start() if edgeui_match else -1
		product_idx = product_match.start() if product_match else -1
		self.assertNotEqual(edgeui_idx, -1)
		self.assertNotEqual(product_idx, -1)
		self.assertLess(edgeui_idx, product_idx)
		self.assertIn("frappe.require(assetName", content)
		self.assertIn("Timed out loading asset", content)
		self.assertIn("Failed to request asset", content)
		self.assertIn("window.EdgeUI", content)
		self.assertIn("window.mountSalespersonPerformanceDashboard", content)
		self.assertIn("retailedge-dashboard-load-error", content)
		self.assertIn("EdgeSuite page controller failed", content)

	def test_edgeui_not_copied(self):
		"""Assert that shared EdgeUI Vue components are not cloned or copied into RetailEdge."""
		retailedge_path = frappe.get_app_path("retailedge")
		for root, _dirs, files in os.walk(retailedge_path):
			for file in files:
				if file.startswith("Edge") and file.endswith(".vue"):
					self.fail(f"Found cloned EdgeUI component {file} inside RetailEdge at {root}")

	def test_aggregation_api_returns_structured_data(self):
		"""Verify get_salesperson_performance API logic returns expected structures."""
		from retailedge.salesperson_performance import get_salesperson_performance

		try:
			res = get_salesperson_performance(
				{"from_date": "2026-07-01", "to_date": "2026-07-06", "limit": 5, "offset": 0}
			)
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
			retailedge_path,
			"public",
			"js",
			"salesperson_performance_dashboard",
			"SalespersonPerformanceDashboard.vue",
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path) as f:
			content = f.read()
		self.assertNotIn("retailedge.branch_performance.get_candidate_branches", content)

	def test_frontend_uses_layout_components_and_identity(self):
		"""Verify frontend uses EdgeAppShell, EdgePageLayout, EdgeFilterBar and sets product identity."""
		retailedge_path = frappe.get_app_path("retailedge")
		vue_path = os.path.join(
			retailedge_path,
			"public",
			"js",
			"salesperson_performance_dashboard",
			"SalespersonPerformanceDashboard.vue",
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path) as f:
			content = f.read()

		self.assertIn("EdgeAppShell", content)
		self.assertIn("EdgePageLayout", content)
		self.assertIn("EdgeFilterBar", content)
		self.assertIn('product="retailedge"', content)
		self.assertIn('data-edge-product="retailedge"', content)

	def test_frontend_references_safe_resolver(self):
		"""Verify SalespersonPerformanceDashboard.vue prefers runtime EdgeUI with local build-safe wrappers."""
		retailedge_path = frappe.get_app_path("retailedge")
		vue_path = os.path.join(
			retailedge_path,
			"public",
			"js",
			"salesperson_performance_dashboard",
			"SalespersonPerformanceDashboard.vue",
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path) as f:
			content = f.read()
		self.assertIn("localEdgeUIComponents", content)
		self.assertIn("resolveEdgeUIComponents", content)
		self.assertIn("window.EdgeUI", content)
		self.assertRegex(content, r'import\s+\{\s*h\s*\}\s+from\s+["\']vue["\']')
		self.assertNotIn("coreedge/coreedge/public/js/edgeui", content)
		self.assertNotIn("../../../../../coreedge", content)

	def test_frontend_has_visible_fallback(self):
		"""Verify SalespersonPerformanceDashboard.vue has a visible fallback path when components resolution fails."""
		retailedge_path = frappe.get_app_path("retailedge")
		vue_path = os.path.join(
			retailedge_path,
			"public",
			"js",
			"salesperson_performance_dashboard",
			"SalespersonPerformanceDashboard.vue",
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path) as f:
			content = f.read()
		self.assertIn("!edgeUIValid", content)
		self.assertIn("EdgeSuite UI failed to load", content)

	def test_loader_uses_public_edgeui_before_product_bundle(self):
		"""Verify salesperson_performance_dashboard.js loader requires EdgeUI before the product bundle."""
		retailedge_path = frappe.get_app_path("retailedge")
		js_path = os.path.join(
			retailedge_path,
			"retailedge",
			"page",
			"salesperson_performance_dashboard",
			"salesperson_performance_dashboard.js",
		)
		self.assertTrue(os.path.exists(js_path))
		with open(js_path) as f:
			content = f.read()
		self.assertNotIn("edgeui.bundle.css", content)
		self.assertNotIn("salesperson_performance.bundle.css", content)
		self.assertIn("edgeui.bundle.js", content)
		self.assertIn("salesperson_performance.bundle.js", content)

		self.assertIn("edgeui.bundle.js", content)
		self.assertIn("salesperson_performance.bundle.js", content)
		self.assertIn("requireAsync", content)
		self.assertIn("retailedge-dashboard-load-error", content)

	def test_frontend_filter_bar_structure_and_labels(self):
		"""Verify that SalespersonPerformanceDashboard.vue has EdgeFilterBar, the correct filter labels, fields, and buttons."""
		retailedge_path = frappe.get_app_path("retailedge")
		vue_path = os.path.join(
			retailedge_path,
			"public",
			"js",
			"salesperson_performance_dashboard",
			"SalespersonPerformanceDashboard.vue",
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path) as f:
			content = f.read()

		self.assertIn("<EdgeFilterBar", content)
		self.assertNotIn("<template #filters>", content)
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
		self.assertIn("Apply / Refresh", content)
		self.assertIn("<EdgeStatCard", content)
		self.assertIn('label="Gross Sales"', content)
		self.assertIn('label="Net Sales"', content)
		self.assertIn('label="Number of Sales Invoices"', content)
		self.assertIn('label="Average Invoice Value"', content)
		self.assertIn('label="Total Discount"', content)
		self.assertIn('label="Outstanding Amount"', content)
		self.assertNotIn('v-if="!metadataLoading"', content)
		self.assertIn(':disabled="metadataLoading"', content)
		fallback_block_start = content.find('v-if="!edgeUIValid"')
		self.assertNotEqual(fallback_block_start, -1)
		fallback_block_end = content.find("<EdgeAppShell", fallback_block_start)
		fallback_content = content[fallback_block_start:fallback_block_end]
		self.assertNotIn("<table", fallback_content)
		self.assertNotIn("dashboard-table", fallback_content)

	def test_loader_loads_css_bundles(self):
		"""Verify salesperson_performance_dashboard.js loader does not request missing bare CSS assets."""
		retailedge_path = frappe.get_app_path("retailedge")
		js_path = os.path.join(
			retailedge_path,
			"retailedge",
			"page",
			"salesperson_performance_dashboard",
			"salesperson_performance_dashboard.js",
		)
		self.assertTrue(os.path.exists(js_path))
		with open(js_path) as f:
			content = f.read()
		self.assertNotIn("edgeui.bundle.css", content)
		self.assertNotIn("salesperson_performance.bundle.css", content)
		self.assertIn("edgeui.bundle.js", content)
		self.assertIn("salesperson_performance.bundle.js", content)

	def test_required_components_resolution_does_not_fallback(self):
		"""Verify SalespersonPerformanceDashboard.vue has local shell components with no CoreEdge private import."""
		retailedge_path = frappe.get_app_path("retailedge")
		vue_path = os.path.join(
			retailedge_path,
			"public",
			"js",
			"salesperson_performance_dashboard",
			"SalespersonPerformanceDashboard.vue",
		)
		self.assertTrue(os.path.exists(vue_path))
		with open(vue_path) as f:
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
		"""Verify R2 native fallback navigation exposes the dashboard with the shared label and route."""
		retailedge_path = frappe.get_app_path("retailedge")
		workspace_path = os.path.join(
			retailedge_path, "retailedge", "workspace", "retailedge", "retailedge.json"
		)
		sidebar_path = os.path.join(
			retailedge_path, "retailedge", "workspace_sidebar", "retailedge", "retailedge.json"
		)
		with open(workspace_path) as f:
			workspace = json.load(f)
		with open(sidebar_path) as f:
			sidebar = json.load(f)

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
		workspace_groups = [row["label"] for row in workspace["links"] if row.get("type") == "Card Break"]
		sidebar_groups = [row["label"] for row in sidebar["items"] if row.get("type") == "Section Break"]
		self.assertEqual(workspace_groups, expected_groups)
		self.assertEqual(sidebar_groups, expected_groups)

		for rows in (workspace["links"], sidebar["items"]):
			links = {row["label"]: row for row in rows if row.get("type") == "Link"}
			self.assertIn("Salesperson Performance", links)
			self.assertEqual(links["Salesperson Performance"]["link_type"], "Page")
			self.assertEqual(links["Salesperson Performance"]["link_to"], "salesperson-performance-dashboard")
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

	def _read_page_js(self):
		retailedge_path = frappe.get_app_path("retailedge")
		js_path = os.path.join(
			retailedge_path,
			"retailedge",
			"page",
			"salesperson_performance_dashboard",
			"salesperson_performance_dashboard.js",
		)
		self.assertTrue(os.path.exists(js_path), "Page JS file does not exist")
		with open(js_path) as f:
			return f.read()

	def test_page_controller_has_boot_console_log(self):
		content = self._read_page_js()
		self.assertIn(
			"[BOOT]",
			content,
			"Page controller must emit a [BOOT] console.log as its first executable statement",
		)
		self.assertIn("Salesperson Performance Dashboard", content, "Boot log must identify the page by name")

	def test_page_controller_top_level_try_catch(self):
		content = self._read_page_js()
		try_idx = content.find("try {")
		pages_match = re.search(r"frappe\.pages\[[\"']salesperson-performance-dashboard[\"']\]", content)
		pages_idx = pages_match.start() if pages_match else -1
		self.assertNotEqual(pages_idx, -1, "Page registration is missing")
		self.assertNotEqual(try_idx, -1, "Top-level try block is missing")
		self.assertLess(
			try_idx, pages_idx, "Top-level try must wrap the frappe.pages registration, not appear after it"
		)

	def test_page_controller_on_page_load_has_try_catch(self):
		content = self._read_page_js()
		self.assertIn("on_page_load", content)
		try_count = content.count("try {")
		self.assertGreaterEqual(
			try_count, 2, "on_page_load must have its own try/catch in addition to the top-level one"
		)

	def test_page_controller_boot_dom_render_before_frappe_require(self):
		content = self._read_page_js()
		active_content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
		active_content = re.sub(r"//.*?\n", "\n", active_content)
		boot_strings = ["EDGEUI BOOT OK", "Loading EdgeSuite UI"]
		boot_idx = min(
			(active_content.find(s) for s in boot_strings if active_content.find(s) != -1), default=-1
		)
		require_idx = active_content.find("frappe.require")
		self.assertNotEqual(
			boot_idx, -1, "Page controller must write a visible boot indicator before frappe.require"
		)
		if require_idx != -1:
			self.assertLess(
				boot_idx,
				require_idx,
				"Boot indicator DOM render must appear before frappe.require calls (check active code, not comments)",
			)

	def test_page_controller_failure_block_rendered_into_wrapper(self):
		content = self._read_page_js()
		self.assertIn(
			"wrapper.appendChild",
			content,
			"Failure block must use wrapper.appendChild to be visible even when page.body is unavailable",
		)

	def test_page_controller_failure_block_has_no_edgeui_dependency(self):
		content = self._read_page_js()
		active_content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
		active_content = re.sub(r"//.*?\n", "\n", active_content)
		catch_positions = []
		pos = 0
		while True:
			idx = active_content.find("} catch (", pos)
			if idx == -1:
				break
			catch_positions.append(idx)
			pos = idx + 1
		self.assertGreater(len(catch_positions), 0, "No catch blocks found")
		for idx in catch_positions:
			block = active_content[idx : idx + 500]
			self.assertNotIn(
				"frappe.require",
				block,
				"Catch/failure block must not call frappe.require - it would create a dependency cycle",
			)

	def test_page_controller_on_page_show_guards_wrapper_page(self):
		content = self._read_page_js()
		self.assertIn("wrapper.page", content)
		has_guard = "if (!page)" in content or "if (!wrapper.page)" in content
		self.assertTrue(
			has_guard,
			"on_page_show must guard against wrapper.page being undefined before accessing page.body",
		)
