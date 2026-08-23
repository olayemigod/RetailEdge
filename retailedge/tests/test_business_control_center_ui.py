from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeBusinessControlCenterUITests(unittest.TestCase):
	def test_page_is_registered_as_standard_edgesuite_page(self):
		page_root = APP_ROOT / "retailedge" / "page" / "business_control_center"
		metadata = json.loads((page_root / "business_control_center.json").read_text())
		script = (page_root / "business_control_center.js").read_text()
		self.assertEqual(metadata["name"], "business-control-center")
		self.assertEqual(metadata["title"], "Business Control Centre")
		self.assertEqual(metadata["roles"], [])
		self.assertIn('frappe.pages["business-control-center"]', script)
		self.assertIn("business_control_center.bundle.js", script)
		self.assertIn("retailedgeMountBusinessControlCenter", script)

	def test_shared_navigation_exposes_business_control_centre_before_action_centre(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		business_control = source.index('"label": "Business Control Centre"')
		action_center = source.index('"label": "Action Centre"')
		self.assertLess(business_control, action_center)
		self.assertIn('"target": "business-control-center"', source)
		self.assertIn('"required_roles": tuple(sorted(ACTION_CENTER_ROLES))', source[business_control:action_center])

	def test_ui_uses_combined_control_endpoint_and_existing_follow_up_api(self):
		source = (APP_ROOT / "public" / "js" / "business_control_center" / "BusinessControlCenter.vue").read_text()
		self.assertIn("retailedge.business_control_center.get_business_control_center", source)
		self.assertIn("retailedge.action_follow_up.update_action_follow_up", source)
		self.assertIn("retailedge.action_center.get_action_center_context", source)
		self.assertIn("item.follow_up_supported === false", source)
		self.assertIn("Financial intelligence is unavailable for this scope", source)
		self.assertIn("operational Action Centre controls remain available", source)

	def test_native_drill_through_obeys_backend_open_mode(self):
		source = (APP_ROOT / "public" / "js" / "business_control_center" / "BusinessControlCenter.vue").read_text()
		self.assertIn('item.open_mode === "new_tab"', source)
		self.assertIn('window.open(route, "_blank", "noopener,noreferrer")', source)
		self.assertIn("window.location.assign(route)", source)
		self.assertNotIn('route.includes("/app/")', source)

	def test_bundle_uses_compiled_vue_components(self):
		bundle = (APP_ROOT / "public" / "js" / "business_control_center.bundle.js").read_text()
		page = (APP_ROOT / "public" / "js" / "business_control_center" / "BusinessControlCenter.vue").read_text()
		row = (APP_ROOT / "public" / "js" / "business_control_center" / "BusinessControlRow.vue").read_text()
		self.assertIn('import BusinessControlCenter from "./business_control_center/BusinessControlCenter.vue"', bundle)
		self.assertIn('import BusinessControlRow from "./BusinessControlRow.vue"', page)
		self.assertIn("<template>", row)
		self.assertNotIn("template: `", page)

	def test_ui_does_not_claim_follow_up_resolves_business_truth(self):
		source = (APP_ROOT / "public" / "js" / "business_control_center" / "BusinessControlCenter.vue").read_text()
		self.assertIn("Follow-up is tracking, not resolution", source)
		self.assertIn("authoritative ERPNext record/report", source)
		self.assertIn("separate RetailEdge Action Follow Up record", source)


if __name__ == "__main__":
	unittest.main()
