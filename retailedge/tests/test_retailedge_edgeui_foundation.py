from __future__ import annotations

import json
import unittest
from pathlib import Path

import frappe

from retailedge import hooks
from retailedge.api.ui_context import _route_for
from retailedge.workspace_home import WorkspaceHomeItem


class TestRetailEdgeEdgeUIFoundation(unittest.TestCase):
	def app_path(self, *parts: str) -> Path:
		return Path(frappe.get_app_path("retailedge", *parts))

	def test_required_apps_and_global_assets_are_registered(self):
		self.assertEqual(hooks.required_apps, ["erpnext", "edgesuite_ui"])
		self.assertIn("/assets/retailedge/js/retailedge_ui_bridge.js", hooks.app_include_js)
		self.assertIn("/assets/retailedge/js/retailedge_product_menu.js", hooks.app_include_js)
		self.assertEqual(hooks.app_home, "/app/retailedge-home")
		self.assertEqual(
			hooks.add_to_apps_screen[0]["has_permission"],
			"retailedge.api.permission.has_app_permission",
		)

	def test_home_page_and_bundle_are_source_controlled(self):
		page_path = self.app_path(
			"retailedge",
			"page",
			"retailedge_home",
			"retailedge_home.json",
		)
		page = json.loads(page_path.read_text())
		self.assertEqual(page["name"], "retailedge-home")
		self.assertEqual(page["module"], "RetailEdge")
		self.assertTrue(page["roles"])
		self.assertTrue(self.app_path("public", "js", "retailedge_home.bundle.js").exists())
		self.assertTrue(
			self.app_path("public", "js", "retailedge_home", "RetailEdgeHome.vue").exists()
		)

	def test_product_bundle_uses_product_vue_and_shared_install_contract(self):
		factory = self.app_path("public", "js", "retailedge_ui", "app_factory.js").read_text()
		self.assertIn('import * as Vue from "vue"', factory)
		self.assertIn('MINIMUM_EDGE_SUITE_UI_VERSION = "0.5.0"', factory)
		self.assertIn("runtime.install(app)", factory)
		self.assertNotIn("coreedge/public", factory.lower())
		self.assertNotIn("../../../../../coreedge", factory.lower())

	def test_home_uses_shared_branch_context_without_persisting_defaults(self):
		home = self.app_path(
			"public",
			"js",
			"retailedge_home",
			"RetailEdgeHome.vue",
		).read_text()
		self.assertIn("EdgeBranchContextSwitcher", home)
		self.assertIn("Filters this Home view only", home)
		self.assertNotIn("set_user_default", home)
		self.assertNotIn("frappe.defaults", home)

	def test_navigation_and_routes_preserve_native_erpnext_targets(self):
		doctype = WorkspaceHomeItem(
			"Sales Invoice",
			"DocType",
			"Sales Invoice",
			"Operations",
			1,
			"operations",
			"ERPNext Link",
		)
		report = WorkspaceHomeItem(
			"Branch Performance",
			"Report",
			"RetailEdge Branch Performance Summary",
			"Reports & Analytics",
			1,
			"manager",
			"RetailEdge Native",
		)
		self.assertEqual(_route_for(doctype), "/app/sales-invoice")
		self.assertEqual(
			_route_for(report),
			"/app/query-report/RetailEdge%20Branch%20Performance%20Summary",
		)

	def test_foundation_does_not_add_business_document_writes(self):
		paths = [
			self.app_path("api", "ui_context.py"),
			self.app_path("ui_identity.py"),
			self.app_path("public", "js", "retailedge_ui_bridge.js"),
			self.app_path("public", "js", "retailedge_product_menu.js"),
		]
		combined = "\n".join(path.read_text() for path in paths).lower()
		for forbidden in (
			"sales invoice").split("|"):
			self.assertNotIn("doc.submit()", combined)
			self.assertNotIn("doc.save()", combined)
			self.assertNotIn("frappe.client.save", combined)
