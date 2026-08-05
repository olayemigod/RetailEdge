from __future__ import annotations

import json
import unittest
from pathlib import Path

from retailedge.edgesuite_ui import NAVIGATION_GROUPS, PROGRAMME_EXPERIENCES, QUICK_ACTIONS


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
				"Home",
				"Sales",
				"Purchases",
				"Inventory",
				"Cash & Banking",
				"Expenses",
				"Customers & Suppliers",
				"Reports & Insights",
				"Setup",
				"Administration",
			],
		)

	def test_administration_group_is_role_restricted(self):
		administration = next(group for group in NAVIGATION_GROUPS if group["key"] == "administration")
		self.assertEqual(administration["required_roles"], ("System Manager",))

	def test_quick_actions_are_unique_and_create_native_documents(self):
		keys = [action["key"] for action in QUICK_ACTIONS]
		self.assertEqual(len(keys), len(set(keys)))
		self.assertTrue(all(action.get("doctype") for action in QUICK_ACTIONS))
		self.assertTrue(all(action.get("mode") in {"available", "native_fallback"} for action in QUICK_ACTIONS))

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

	def test_global_controller_uses_canonical_runtime_and_product_bundles(self):
		controller = (APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js").read_text()
		self.assertLess(controller.index("edgeui.bundle.js"), controller.index("retailedge_business_hub.bundle.js"))
		self.assertIn("assertEdgeSuiteUIRuntime", controller)
		self.assertIn("global.EdgeSuiteUI", controller)
		self.assertNotIn('"edgesuite_ui.bundle.js"', controller)
		self.assertNotIn("global.EdgeUI", controller)

	def test_global_controller_supports_promise_based_frappe_require(self):
		controller = (APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js").read_text()
		self.assertIn("const pending = frappe.require(asset, finish)", controller)
		self.assertIn('typeof pending.then === "function"', controller)
		self.assertIn("pending.then(finish).catch(fail)", controller)
		self.assertIn("if (!wrapper._retailedgeBusinessHub)", controller)
		self.assertIn("return bootBusinessHub(wrapper)", controller)

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
		self.assertNotIn("switch_product_app", menu)
		self.assertNotIn("CoreEdge", menu)

	def test_standard_page_loader_delegates_to_global_controller(self):
		path = APP_ROOT / "retailedge" / "page" / "retailedge_business_hub" / "retailedge_business_hub.js"
		source = path.read_text()
		self.assertIn("window.retailedgeRegisterBusinessHubPage", source)
		self.assertNotIn("frappe.ui.make_app_page", source)

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
