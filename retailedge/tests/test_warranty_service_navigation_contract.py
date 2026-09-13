from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestWarrantyServiceNavigationContract(TestCase):
	def test_service_group_uses_native_permission_aware_destinations(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		group_start = source.index('"key": "service-warranty"')
		group_end = source.index('"key": "suppliers-payables"', group_start)
		group = source[group_start:group_end]

		self.assertEqual(group.count('"key": "service-warranty"'), 1)
		self.assertEqual(group.count('"label": "Warranty Claims"'), 1)
		self.assertEqual(group.count('"label": "Maintenance Schedules"'), 1)
		self.assertEqual(group.count('"label": "Maintenance Visits"'), 1)
		self.assertIn('"target_type": "DocType", "target": "Warranty Claim"', group)
		self.assertIn('"target_type": "DocType", "target": "Maintenance Schedule"', group)
		self.assertIn('"target_type": "DocType", "target": "Maintenance Visit"', group)
		self.assertNotIn("required_roles", group)

		self.assertIn('if target_type == "DocType":', source)
		self.assertIn('_has_permission_cached(target, "read", permission_cache)', source)

	def test_new_claim_action_is_native_and_create_permission_gated(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		action_start = source.index('"key": "new-warranty-claim"')
		action_end = source.index('"key": "transfer-stock"', action_start)
		action = source[action_start:action_end]

		self.assertEqual(source.count('"key": "new-warranty-claim"'), 1)
		self.assertIn('"label": "New Warranty Claim"', action)
		self.assertIn('"doctype": "Warranty Claim"', action)
		self.assertIn('"mode": "native_fallback"', action)
		self.assertIn('_has_permission_cached(doctype, "create", permission_cache)', source)

		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "RetailEdgeBusinessHub.vue"
		).read_text()
		self.assertIn("frappe.new_doc(action.doctype);", component)

	def test_retailedge_does_not_wrap_native_service_lifecycle(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()

		for forbidden in (
			"make_maintenance_visit",
			"generate_maintenance_schedule",
			"create_maintenance_schedule",
			"create_maintenance_visit",
			"close_warranty_claim",
			"resolve_warranty_claim",
			'frappe.get_doc("Warranty Claim"',
			'frappe.new_doc("Warranty Claim"',
			"ignore_permissions",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	import unittest

	unittest.main()
