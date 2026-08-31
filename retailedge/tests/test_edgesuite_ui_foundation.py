from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from retailedge.edgesuite_ui import (
	NAVIGATION_GROUPS,
	PROGRAMME_EXPERIENCES,
	QUICK_ACTIONS,
	_get_permitted_navigation_groups,
	_get_permitted_quick_actions,
)
from retailedge.workspace_home import HOME_SECTIONS, HOME_WORKSPACE_ITEMS

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeEdgeSuiteUIFoundationTests(unittest.TestCase):
	def test_programme_experiences_follow_agreed_order(self):
		self.assertEqual(
			[experience["key"] for experience in PROGRAMME_EXPERIENCES],
			["navigate", "act", "operate", "understand", "respond"],
		)

	def test_navigation_uses_approved_business_architecture(self):
		self.assertEqual(
			[group["label"] for group in NAVIGATION_GROUPS],
			[
				"Home",
				"Sell",
				"Buy",
				"Stock",
				"Assets",
				"Money",
				"Expenses",
				"Customers",
				"Suppliers & Payables",
				"Insights",
				"Review & Approvals",
				"Accounting",
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

	def test_customers_suppliers_stock_and_controls_have_single_business_home(self):
		groups = {group["key"]: group for group in NAVIGATION_GROUPS}
		self.assertEqual(
			{item["target"] for item in groups["customers"]["items"]},
			{"Customer", "customer-receivables", "Accounts Receivable"},
		)
		self.assertEqual(
			{item["target"] for item in groups["suppliers-payables"]["items"]},
			{"Supplier", "supplier-payables", "Payment Order", "Accounts Payable"},
		)
		self.assertIn(
			"RetailEdge Stock Movement History",
			{item["target"] for item in groups["stock"]["items"]},
		)
		self.assertNotIn(
			"RetailEdge Stock Movement History",
			{item["target"] for item in groups["insights"]["items"]},
		)
		self.assertIn(
			"RetailEdge Bank Transaction Match",
			{item["target"] for item in groups["review-approvals"]["items"]},
		)
		self.assertNotIn(
			"RetailEdge Bank Transaction Match",
			{item["target"] for item in groups["money"]["items"]},
		)

	def test_accounting_and_setup_are_role_restricted(self):
		groups = {group["key"]: group for group in NAVIGATION_GROUPS}
		self.assertEqual(
			set(groups["accounting"]["required_roles"]),
			{"Accounts User", "Accounts Manager", "System Manager"},
		)
		self.assertEqual(groups["setup"]["required_roles"], ("System Manager",))
		self.assertIn("Journal Entry", {item["target"] for item in groups["accounting"]["items"]})

	def test_business_navigation_excludes_technical_and_edgepay_surfaces(self):
		keys = {group["key"] for group in NAVIGATION_GROUPS}
		targets = {
			item["target"]
			for group in NAVIGATION_GROUPS
			for item in group["items"]
		}
		self.assertNotIn("administration", keys)
		self.assertNotIn("RetailEdge Bank Match Batch Job", targets)
		self.assertNotIn("Error Log", targets)
		self.assertFalse(any("EdgePay" in target for target in targets))

	def test_runtime_workspace_uses_compact_business_fallback_taxonomy(self):
		self.assertEqual(
			HOME_SECTIONS,
			(
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
			),
		)
		targets = {item.link_to for item in HOME_WORKSPACE_ITEMS}
		self.assertIn("retailedge-business-hub", targets)
		self.assertNotIn("RetailEdge Bank Match Batch Job", targets)
		self.assertNotIn("Error Log", targets)
		self.assertNotIn("Journal Entry", targets)
		self.assertNotIn("Expense Claim", targets)

	def test_navigation_and_quick_actions_share_request_local_metadata_cache(self):
		pos_capabilities = SimpleNamespace(
			provider="erpnext",
			start_link_type="Page",
			start_target="point-of-sale",
			start_url=None,
			opening_doctype="POS Opening Entry",
			closing_doctype="POS Closing Entry",
		)
		target_cache = {}
		permission_cache = {}
		with (
			patch("retailedge.edgesuite_ui._target_exists", return_value=True) as mock_exists,
			patch("retailedge.edgesuite_ui._has_permission", return_value=True),
		):
			_get_permitted_navigation_groups(
				{"System Manager"},
				target_cache=target_cache,
				permission_cache=permission_cache,
				pos_capabilities=pos_capabilities,
			)
			_get_permitted_quick_actions(
				target_cache=target_cache,
				permission_cache=permission_cache,
			)

		self.assertEqual(mock_exists.call_args_list.count(call("DocType", "Sales Invoice")), 1)
		self.assertEqual(mock_exists.call_args_list.count(call("DocType", "Payment Entry")), 1)
		self.assertEqual(mock_exists.call_args_list.count(call("DocType", "Purchase Invoice")), 1)

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
		self.assertIn("Loading Business Hub", controller)
		self.assertIn("Business Hub failed to load", controller)

	def test_business_hub_uses_one_edgesuite_navigation_surface(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "RetailEdgeBusinessHub.vue"
		).read_text()
		controller = (APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js").read_text()
		self.assertIn(':hideNativeSidebar="true"', component)
		self.assertIn("items: (group.items || [])", component)
		self.assertIn('group.key !== "home"', component)
		self.assertNotIn(".slice(0, 8)", component)
		self.assertNotIn("Professional business menu", component)
		self.assertNotIn("navigation-grid", component)
		self.assertIn("suppressNativePageChrome", controller)
		self.assertIn('data-retailedge-shell-suppressed', controller)
		self.assertIn('pageHead.hide()', controller)

	def test_business_hub_and_waffle_share_short_lived_context_request(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "RetailEdgeBusinessHub.vue"
		).read_text()
		menu = (APP_ROOT / "public" / "js" / "retailedge_product_menu.bundle.js").read_text()
		for source in (component, menu):
			self.assertIn("__retailedgeBusinessHubContextCache", source)
			self.assertIn("__retailedgeBusinessHubContextRequest", source)
			self.assertIn("CONTEXT_CACHE_TTL_MS", source)
		self.assertIn("retailedgeGetBusinessHubContext", component)
		self.assertIn("window.retailedgeGetBusinessHubContext = fetchContext", menu)

	def test_backend_context_declares_request_cached_performance_profile(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		self.assertIn('"performance_profile": "r2_request_cached"', source)
		self.assertIn("target_cache", source)
		self.assertIn("permission_cache", source)
		self.assertIn("pos_capabilities=pos_capabilities", source)

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
		self.assertIn('"review-approvals"', menu)
		self.assertIn('"suppliers-payables"', menu)
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