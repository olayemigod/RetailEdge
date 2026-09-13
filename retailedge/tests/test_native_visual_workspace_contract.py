from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from retailedge.edgesuite_ui import NAVIGATION_GROUPS

APP_ROOT = Path(__file__).resolve().parents[1]


class TestNativeVisualWorkspaceContract(TestCase):
	def test_c24_c25_c26_have_primary_edgesuite_workspaces_and_native_fallbacks(self):
		groups = {group["key"]: list(group["items"]) for group in NAVIGATION_GROUPS}
		self.assertIn(("Page", "service-warranty-control"), [(item["target_type"], item["target"]) for item in groups["service-warranty"]])
		self.assertIn(("Page", "sales-team-control"), [(item["target_type"], item["target"]) for item in groups["sell"]])
		self.assertIn(("Page", "budget-control"), [(item["target_type"], item["target"]) for item in groups["accounting"]])

		for expected in (
			("DocType", "Warranty Claim"),
			("DocType", "Maintenance Schedule"),
			("DocType", "Maintenance Visit"),
			("DocType", "Sales Person"),
			("DocType", "Sales Partner"),
			("Report", "Sales Person Commission Summary"),
			("Report", "Sales Partner Commission Summary"),
			("Report", "Sales Person Target Variance Based On Item Group"),
			("Report", "Sales Partner Target Variance based on Item Group"),
			("DocType", "Budget"),
			("Report", "Budget Variance Report"),
			("DocType", "Cost Center"),
		):
			self.assertTrue(any(expected in [(item["target_type"], item["target"]) for item in items] for items in groups.values()))

	def test_all_three_pages_mount_the_shared_edgesuite_workspace_bundle(self):
		for page_name in ("service_warranty_control", "sales_team_control", "budget_control"):
			page_dir = APP_ROOT / "retailedge" / "page" / page_name
			self.assertTrue((page_dir / f"{page_name}.json").exists())
			source = (page_dir / f"{page_name}.js").read_text()
			self.assertIn('"edgeui.bundle.js"', source)
			self.assertIn('"native_visual_workspaces.bundle.js"', source)
			self.assertIn("mountNativeERPNextWorkspace", source)

		component = (APP_ROOT / "public" / "js" / "native_visual_workspaces" / "NativeERPNextWorkspace.vue").read_text()
		self.assertIn("<EdgeAppShell", component)
		self.assertIn("frappe.new_doc(source.target)", component)
		self.assertIn('frappe.set_route("Form", source.target, row.name)', component)

	def test_workspace_backend_is_read_only_and_permission_aware(self):
		source = (APP_ROOT / "native_visual_workspaces.py").read_text()
		self.assertIn('frappe.has_permission(doctype, "read")', source)
		self.assertIn("frappe.get_list(", source)
		self.assertIn("get_report_doc(source[\"target\"])", source)
		for forbidden in (
			"ignore_permissions",
			"frappe.db.commit",
			"frappe.get_doc(",
			"frappe.new_doc(",
			".insert(",
			".submit(",
			".save(",
			"GL Entry",
			"Stock Ledger Entry",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	import unittest

	unittest.main()
