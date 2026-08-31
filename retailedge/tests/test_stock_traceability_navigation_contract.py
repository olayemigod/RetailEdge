from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.edgesuite_ui import NAVIGATION_GROUPS

APP_ROOT = Path(__file__).resolve().parents[1]


class TestStockTraceabilityNavigationContract(unittest.TestCase):
	def setUp(self):
		self.groups = {group["key"]: group for group in NAVIGATION_GROUPS}
		self.stock_items = list(self.groups["stock"]["items"])
		self.stock_targets = [item["target"] for item in self.stock_items]
		self.stock_labels = [item["label"] for item in self.stock_items]

	def test_batch_and_serial_destinations_are_native_and_ordered(self):
		batches = [item for item in self.stock_items if item["label"] == "Batches"]
		serials = [item for item in self.stock_items if item["label"] == "Serial Numbers"]

		self.assertEqual(batches, [{"label": "Batches", "target_type": "DocType", "target": "Batch", "icon": "layers"}])
		self.assertEqual(
			serials,
			[{"label": "Serial Numbers", "target_type": "DocType", "target": "Serial No", "icon": "clipboard"}],
		)
		self.assertLess(self.stock_labels.index("Stock Locations"), self.stock_labels.index("Batches"))
		self.assertLess(self.stock_labels.index("Batches"), self.stock_labels.index("Serial Numbers"))
		self.assertLess(self.stock_labels.index("Serial Numbers"), self.stock_labels.index("Stock Movement History"))

	def test_traceability_targets_have_one_business_home_and_keep_internal_bundle_hidden(self):
		all_targets = [
			item["target"]
			for group in NAVIGATION_GROUPS
			for item in group["items"]
		]
		self.assertEqual(all_targets.count("Batch"), 1)
		self.assertEqual(all_targets.count("Serial No"), 1)
		self.assertNotIn("Serial and Batch Bundle", all_targets)

	def test_traceability_navigation_reuses_native_read_permission_path_only(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		self.assertIn(
			'return _doctype_exists_cached(target, target_cache) and _has_permission_cached(target, "read", permission_cache)',
			source,
		)
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
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
