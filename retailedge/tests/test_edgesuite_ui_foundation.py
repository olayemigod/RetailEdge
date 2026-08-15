from __future__ import annotations

import json
import unittest
from pathlib import Path

from retailedge.edgesuite_ui import NAVIGATION_GROUPS, PROGRAMME_EXPERIENCES, QUICK_ACTIONS
from retailedge.workspace_home import HOME_SECTIONS, HOME_WORKSPACE_ITEMS

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeEdgeSuiteUIFoundationTests(unittest.TestCase):
	def test_programme_experiences_follow_agreed_order(self):
		self.assertEqual(
			[experience["key"] for experience in PROGRAMME_EXPERIENCES],
			["navigate", "act", "operate", "understand", "respond"],
		)

	def test_navigation_uses_professional_business_groups(self):
		labels = [group["label"] for group in NAVIGATION_GROUPS]
		self.assertEqual(
			labels,
			[
				"Dashboard",
				"Sales",
				"Purchases",
				"Inventory",
				"Cash & Banking",
				"Expenses",
				"Customers & Suppliers",
				"Reviews & Controls",
				"Reports & Insights",
				"Setup",
			],
		)

	def test_navigation_targets_are_not_duplicated_across_business_groups(self):
		targets = [
			(item["target_type"], item["target"])
			for group in NAVIGATION_GROUPS
			for item in group["items"]
		]
		self.assertEqual(len(targets), len(set(targets)))

	def test_navigation_classifies_relationships_reviews_and_expenses_once(self):
		groups = {group["key"]: group for group in NAVIGATION_GROUPS}

		self.assertNotIn(
			"Customer",
			{item["target"] for item in groups["sales"]["items"]},
		)
		self.assertNotIn(
			"Supplier",
			{item["target"] for item in groups["purchases"]["items"]},
		)
		self.assertIn(
			"Customer",
			{item["target"] for item in groups["customers-suppliers"]["items"]},
		)
		self.assertIn(
			"Supplier",
			{item["target"] for item in groups["customers-suppliers"]["items"]},
		)
		self.assertIn(
			"RetailEdge Bank Transaction Match",
			{item["target"] for item in groups["reviews-controls"]["items"]},
		)
		self.assertNotIn(
			"RetailEdge Bank Transaction Match",
			{item["target"] for item in groups["cash-banking"]["items"]},
		)
		self.assertIn(
			"RetailEdge Cashier Expense",
			{item["target"] for item in groups["expenses"]["items"]},
		)
		self.assertNotIn(
			"RetailEdge Cashier Expense",
			{item["target"] for item in groups["cash-banking"]["items"]},
		)

	def test_business_navigation_excludes_technical_administration(self):
		keys = {group["key"] for group in NAVIGATION_GROUPS}
		targets = {
			item["target"]
			for group in NAVIGATION_GROUPS
			for item in group["items"]
		}
		self.assertNotIn("administration", keys)
		self.assertNotIn("RetailEdge Bank Match Batch Job", targets)
		self.assertNotIn("Error Log", targets)

	def test_workspace_home_uses_matching_business_taxonomy(self):
		self.assertEqual(
			HOME_SECTIONS,
			(
				"Dashboard",
				"Sales & POS",
				"Purchases",
				"Inventory",
				"Cash & Banking",
				"Expenses",
				"Customers & Suppliers",
				"Reviews & Controls",
				"Reports & Insights",
				"Setup",
			),
		)
		targets = {item.link_to for item in HOME_WORKSPACE_ITEMS}
		self.assertNotIn("RetailEdge Bank Match Batch Job", targets)
		self.assertNotIn("Error Log", targets)
		self.assertNotIn("Journal Entry", targets)

	def test_sidebar_fixture_uses_same_business_classification(self):
		path = (
			APP_ROOT
			/ "retailedge"
			/ "workspace_sidebar"
			/ "retailedge"
			/ "retailedge.json"
		)
		data = json.loads(path.read_text())
		sections = [
			row["label"]
			for row in data["items"]
			if row.get("type") == "Section Break"
		]
		self.assertEqual(
			sections,
			[
				"Dashboard",
				"Sales & POS",
				"Purchases",
				"Inventory",
				"Cash & Banking",
				"Expenses",
				"Customers & Suppliers",
				"Reviews & Controls",
				"Reports & Insights",
				"Setup",
			],
		)
		targets = [
			row.get("link_to")
			for row in data["items"]
			if row.get("type") == "Link"
		]
		self.assertEqual(targets.count("Customer"), 1)
		self.assertEqual(targets.count("Supplier"), 1)
		self.assertNotIn("RetailEdge Bank Match Batch Job", targets)
		self.assertNotIn("Error Log", targets)
		self.assertNotIn("Journal Entry", targets)

	def test_quick_actions_are_unique_and_create_native_documents(self):
		keys = [action["key"] for action in QUICK_ACTIONS]
		self.assertEqual(len(keys), len(set(keys)))
		self.assertTrue(all(action.get("doctype") for action in QUICK_ACTIONS))
		self.assertTrue(
			all(action.get("mode") in {"available", "native_fallback"} for action in QUICK_ACTIONS)
		)

	def test_business_hub_page_definition_is_standard(self):
		path = APP_ROOT / "retailedge" / "page" / "retailedge_business_hub" / "retailedge_business_hub.json"
		data = json.loads(path.read_text())
		self.assertEqual(data["name"], "retailedge-business-hub")
		self.assertEqual(data["standard"], "Yes")
		self.assertIn("RetailEdge Manager", {row["role"] for row in data["roles"]})

	def test_retailedge_requires_standalone_edgesuite_ui_app(self):
		hooks = (APP_ROOT / "hooks.py").read_text()
		self.assertIn('required_apps = ["edgesuite_ui"]', hooks)
		self.assertNotIn('required_apps = ["coreedge"]', hooks)

	def test_business_hub_controller_is_loaded_globally_in_desk(self):
		hooks = (APP_ROOT / "hooks.py").read_text()
		self.assertIn("retailedge_business_hub_page.js", hooks)
		controller = (APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js").read_text()
		self.assertIn('const PAGE_NAME = "retailedge-business-hub"', controller)
		self.assertIn("retailedgeRegisterBusinessHubPage", controller)
		self.assertIn("retailedgeBootBusinessHubPage", controller)
		self.assertIn("__retailedge_business_hub_registered", controller)
		self.assertIn("Loading RetailEdge Business Hub", controller)
		self.assertIn("RetailEdge Business Hub failed to load", controller)

	def test_business_hub_uses_single_edgesuite_shell(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "RetailEdgeBusinessHub.vue"
		).read_text()
		controller = (APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js").read_text()

		self.assertIn(':hideNativeSidebar="true"', component)
		self.assertIn(".map((group) => ({", component)
		self.assertIn("items: (group.items || [])", component)
		self.assertNotIn(".slice(0, 8)", component)
		self.assertIn("suppressNativePageChrome", controller)
		self.assertIn('data-retailedge-shell-suppressed', controller)
		self.assertIn('pageHead.hide()', controller)

	def test_global_controller_does_not_preempt_frappe_page_container_creation(self):
		controller = (APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js").read_text()
		self.assertNotIn(
			"frappe.pages[PAGE_NAME] = frappe.pages[PAGE_NAME] || {}",
			controller,
		)
		self.assertIn("const wrapper = frappe.pages[PAGE_NAME]", controller)
		self.assertIn("wrapper instanceof global.HTMLElement", controller)

	def test_global_controller_uses_canonical_runtime_and_product_bundles(self):
		controller = (APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js").read_text()
		self.assertLess(
			controller.index("edgeui.bundle.js"), controller.index("retailedge_business_hub.bundle.js")
		)
		self.assertIn("assertEdgeSuiteUIRuntime", controller)
		self.assertIn("global.EdgeSuiteUI", controller)
		self.assertNotIn('"edgesuite_ui.bundle.js"', controller)
		self.assertNotIn("global.EdgeUI", controller)

	def test_global_controller_supports_promise_based_frappe_require(self):
		controller = (APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js").read_text()
		self.assertIn("const pending = frappe.require(asset, finish)", controller)
		self.assertIn('typeof pending.then === "function"', controller)
		self.assertIn("pending.then(finish).catch(fail)", controller)
		self.assertIn("if (!currentWrapper._retailedgeBusinessHub)", controller)
		self.assertIn("return bootBusinessHub(currentWrapper)", controller)

	def test_edge_suite_waffle_is_booted_across_desk(self):
		controller = (APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js").read_text()
		self.assertIn('const PRODUCT_MENU_ASSET = "retailedge_product_menu.bundle.js"', controller)
		self.assertIn("retailedgeBootProductMenu", controller)
		self.assertIn("retailedgeInstallProductMenu", controller)
		self.assertIn("bootProductMenu()", controller)

	def test_product_menu_uses_permission_aware_navigation_without_product_switching(self):
		menu = (APP_ROOT / "public" / "js" / "retailedge_product_menu.bundle.js").read_text()
		self.assertIn("window.EdgeSuiteUI", menu)
		self.assertNotIn("window.EdgeUI", menu)
		self.assertIn("registerProductMenu", menu)
		self.assertIn("refreshProductMenu", menu)
		self.assertIn("mountProductMenu", menu)
		self.assertIn("get_retailedge_business_hub_context", menu)
		self.assertIn("data.navigation_groups", menu)
		self.assertIn("product: PRODUCT", menu)
		self.assertIn('"reviews-controls"', menu)
		self.assertNotIn("administration:", menu)
		self.assertNotIn("switch_product_app", menu)
		self.assertNotIn("CoreEdge", menu)

	def test_standard_page_loader_boots_current_wrapper_and_route_bridge(self):
		path = APP_ROOT / "retailedge" / "page" / "retailedge_business_hub" / "retailedge_business_hub.js"
		source = path.read_text()
		self.assertIn("window.retailedgeRegisterBusinessHubPage", source)
		self.assertIn("window.retailedgeBootBusinessHubPage", source)
		self.assertIn("retailedge_business_hub_route_bridge.js", source)
		self.assertNotIn("frappe.ui.make_app_page", source)
		self.assertIn("const wrapper = window.frappe?.pages?.[PAGE_NAME]", source)
		self.assertNotIn("?.wrapper", source)

	def test_route_bridge_recovers_when_page_was_open_before_controller_registration(self):
		bridge = (APP_ROOT / "public" / "js" / "retailedge_business_hub_route_bridge.js").read_text()
		self.assertIn('const PAGE_NAME = "retailedge-business-hub"', bridge)
		self.assertIn("frappe?.pages?.[PAGE_NAME]", bridge)
		self.assertIn("retailedgeBootBusinessHubPage", bridge)
		self.assertIn("page-change", bridge)
		self.assertIn("router?.on", bridge)
		self.assertIn("MAX_ATTEMPTS", bridge)
		self.assertNotIn("CoreEdge", bridge)

	def test_route_bridge_never_mounts_into_an_unrelated_visible_desk_page(self):
		for filename in (
			"retailedge_business_hub_route_bridge.js",
			"retailedge_business_hub_route_bridge_v2.js",
		):
			with self.subTest(filename=filename):
				bridge = (APP_ROOT / "public" / "js" / filename).read_text()
				self.assertNotIn("resolveDeskContentRoot", bridge)
				self.assertNotIn('"single visible .page-container"', bridge)
				self.assertNotIn('querySelectorAll?.(".page-container")', bridge)
				self.assertIn("definition instanceof global.HTMLElement", bridge)
				self.assertIn("state.booted = false", bridge)

	def test_product_bundle_and_vue_use_canonical_runtime_only(self):
		bundle = (APP_ROOT / "public" / "js" / "retailedge_business_hub.bundle.js").read_text()
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
		).read_text()
		for source in (bundle, component):
			self.assertIn("window.EdgeSuiteUI", source)
			self.assertNotIn("window.EdgeUI", source)

	def test_product_switching_is_suspended_but_product_menu_is_not(self):
		path = APP_ROOT / "edgesuite_ui.py"
		source = path.read_text()
		self.assertIn('"product_switcher_enabled": False', source)
		self.assertNotIn("switch_product_app", source)
		self.assertTrue((APP_ROOT / "public" / "js" / "retailedge_product_menu.bundle.js").exists())


if __name__ == "__main__":
	unittest.main()
