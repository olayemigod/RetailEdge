from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.edgesuite_ui import NAVIGATION_GROUPS

APP_ROOT = Path(__file__).resolve().parents[1]
OVERVIEW_TARGET = "stock-traceability-control"
NATIVE_TARGETS = ["Batch", "Serial No"]
REPORT_TARGETS = ["Batch Item Expiry Status", "Available Batch Report", "Available Serial No"]


class TestStockTraceabilityNavigationContract(unittest.TestCase):
	def setUp(self):
		self.groups = {group["key"]: group for group in NAVIGATION_GROUPS}
		self.stock_items = list(self.groups["stock"]["items"])
		self.stock_targets = [item["target"] for item in self.stock_items]
		self.stock_labels = [item["label"] for item in self.stock_items]

	def test_traceability_uses_edgesuite_overview_and_keeps_native_fallbacks_ordered(self):
		self.assertIn(
			{"label": "Stock Traceability", "target_type": "Page", "target": OVERVIEW_TARGET, "icon": "search"},
			self.stock_items,
		)
		self.assertIn(
			{"label": "Batches", "target_type": "DocType", "target": "Batch", "icon": "layers"},
			self.stock_items,
		)
		self.assertIn(
			{"label": "Serial Numbers", "target_type": "DocType", "target": "Serial No", "icon": "clipboard"},
			self.stock_items,
		)
		self.assertLess(self.stock_labels.index("Stock Locations"), self.stock_labels.index("Stock Traceability"))
		self.assertLess(self.stock_labels.index("Stock Traceability"), self.stock_labels.index("Batches"))
		self.assertLess(self.stock_labels.index("Batches"), self.stock_labels.index("Serial Numbers"))
		self.assertLess(self.stock_labels.index("Serial Numbers"), self.stock_labels.index("Stock Movement History"))

	def test_traceability_targets_have_one_business_home_and_keep_internal_bundle_hidden(self):
		all_targets = [item["target"] for group in NAVIGATION_GROUPS for item in group["items"]]
		self.assertEqual(all_targets.count(OVERVIEW_TARGET), 1)
		for target in NATIVE_TARGETS:
			self.assertEqual(all_targets.count(target), 1)
		self.assertNotIn("Serial and Batch Bundle", all_targets)

	def test_traceability_page_uses_governed_edgesuite_runtime(self):
		page_dir = APP_ROOT / "retailedge" / "page" / "stock_traceability_control"
		self.assertTrue((page_dir / "stock_traceability_control.json").exists())
		page = (page_dir / "stock_traceability_control.js").read_text()
		self.assertIn('"edgeui.bundle.js"', page)
		self.assertIn('"native_visual_workspaces.bundle.js"', page)
		self.assertIn('"stock-traceability"', page)
		self.assertIn("mountNativeERPNextWorkspace", page)
		self.assertNotIn("window.EdgeUI", page)
		self.assertNotIn("frappe.ui.Dialog", page)
		self.assertNotIn("frappe.prompt", page)
		self.assertNotIn("frappe.msgprint", page)

	def test_workspace_reuses_native_permissions_and_report_authority(self):
		navigation_source = (APP_ROOT / "edgesuite_ui.py").read_text()
		workspace_source = (APP_ROOT / "native_visual_workspaces.py").read_text()
		self.assertIn(
			'return _doctype_exists_cached(target, target_cache) and _has_permission_cached(target, "read", permission_cache)',
			navigation_source,
		)
		self.assertIn('frappe.has_permission(doctype, "read")', workspace_source)
		self.assertIn("get_report_doc(source[\"target\"])", workspace_source)
		for report in REPORT_TARGETS:
			self.assertIn(f'"target": "{report}"', workspace_source)

	def test_retailedge_does_not_create_parallel_traceability_or_stock_writes(self):
		workspace_source = (APP_ROOT / "native_visual_workspaces.py").read_text()
		for forbidden in (
			"prepare_batch",
			"create_batch",
			"move_batch",
			"split_batch",
			"create_serial_no",
			'frappe.get_doc("Batch"',
			'frappe.get_doc("Serial No"',
			"ignore_permissions",
			"frappe.db.commit",
			".insert(",
			".submit(",
			"Stock Ledger Entry",
		):
			self.assertNotIn(forbidden, workspace_source)


if __name__ == "__main__":
	unittest.main()
