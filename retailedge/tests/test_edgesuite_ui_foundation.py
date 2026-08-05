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

	def test_page_loader_requires_canonical_edgesuite_ui_before_product_bundle(self):
		path = APP_ROOT / "retailedge" / "page" / "retailedge_business_hub" / "retailedge_business_hub.js"
		source = path.read_text()
		self.assertLess(source.index("edgesuite_ui.bundle.js"), source.index("retailedge_business_hub.bundle.js"))
		self.assertIn("assertEdgeSuiteUIRuntime", source)
		self.assertIn("window.EdgeSuiteUI", source)
		self.assertNotIn("'edgeui.bundle.js'", source)
		self.assertNotIn("window.EdgeUI", source)
		self.assertIn("failed to load", source)

	def test_product_bundle_and_vue_use_canonical_runtime_only(self):
		bundle = (APP_ROOT / "public" / "js" / "retailedge_business_hub.bundle.js").read_text()
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
		).read_text()
		for source in (bundle, component):
			self.assertIn("window.EdgeSuiteUI", source)
			self.assertNotIn("window.EdgeUI", source)

	def test_product_switcher_is_explicitly_suspended_in_api_contract(self):
		path = APP_ROOT / "edgesuite_ui.py"
		source = path.read_text()
		self.assertIn('"product_switcher_enabled": False', source)
		self.assertNotIn("switch_product_app", source)


if __name__ == "__main__":
	unittest.main()
