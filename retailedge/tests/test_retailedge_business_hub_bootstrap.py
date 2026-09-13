from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
HOOKS = APP_ROOT / "hooks.py"
BOOTSTRAP = APP_ROOT / "public" / "js" / "retailedge_business_hub_bootstrap.js"
CONTROLLER = APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js"


class RetailEdgeBusinessHubBootstrapTests(unittest.TestCase):
	def test_global_hooks_load_bootstrap_not_controller(self):
		hooks = HOOKS.read_text(encoding="utf-8")
		self.assertIn('/assets/retailedge/js/retailedge_business_hub_bootstrap.js', hooks)
		self.assertNotIn('/assets/retailedge/js/retailedge_business_hub_page.js",\n\t"/assets/retailedge/js/retailedge_reporting_actions.js', hooks)

	def test_bootstrap_requires_full_authenticated_desk_runtime(self):
		bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
		self.assertIn('currentUser() !== "Guest"', bootstrap)
		self.assertIn('typeof global.__ === "function"', bootstrap)
		self.assertIn('typeof global.frappe.require === "function"', bootstrap)
		self.assertIn('global.frappe.pages', bootstrap)
		self.assertIn('typeof global.frappe.ui.make_app_page === "function"', bootstrap)
		self.assertIn('global.frappe.require(CONTROLLER_ASSET)', bootstrap)
		self.assertNotIn('__("', bootstrap)

	def test_controller_remains_a_separate_desk_asset(self):
		controller = CONTROLLER.read_text(encoding="utf-8")
		self.assertIn('global.retailedgeRegisterBusinessHubPage = registerPage', controller)
		self.assertIn('global.retailedgeBootProductMenu = bootProductMenu', controller)


if __name__ == "__main__":
	unittest.main()
