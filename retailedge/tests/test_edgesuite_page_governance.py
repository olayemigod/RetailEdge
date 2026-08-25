from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

# RetailEdge-owned Pages added or materially rebuilt after the EdgeSuite single-shell
# foundation must be registered here and satisfy the EdgeSuite mount contract. Native
# ERPNext DocTypes/Reports remain valid explicit advanced fallbacks; this governs
# RetailEdge-owned Frappe Page experiences.
EDGE_SUITE_REQUIRED_PAGES = {
	"operating_context": {
		"loader": APP_ROOT / "retailedge" / "page" / "operating_context" / "operating_context.js",
		"bundle": APP_ROOT / "public" / "js" / "operating_context.bundle.js",
		"component": APP_ROOT / "public" / "js" / "operating_context" / "OperatingContext.vue",
	},
}


class TestEdgeSuitePageGovernance(unittest.TestCase):
	def test_required_pages_use_edgesuite_mount_contract(self):
		for page_name, files in EDGE_SUITE_REQUIRED_PAGES.items():
			with self.subTest(page=page_name):
				loader = files["loader"].read_text(encoding="utf-8")
				bundle = files["bundle"].read_text(encoding="utf-8")
				component = files["component"].read_text(encoding="utf-8")

				self.assertIn('"edgeui.bundle.js"', loader)
				self.assertIn('"operating_context.bundle.js"', loader)
				self.assertIn("window.EdgeSuiteUI", loader)
				self.assertIn("mountRetailEdgeOperatingContext", loader)
				self.assertNotIn('className = "frappe-card"', loader)

				self.assertIn("createEdgeApp", bundle)
				self.assertIn("OperatingContext.vue", bundle)
				self.assertIn("EdgeAppShell", component)
				self.assertIn("EdgePageLayout", component)
				self.assertIn("EdgePageHeader", component)
				self.assertIn("EdgeLoadingState", component)
				self.assertIn("EdgeErrorState", component)
				self.assertIn("retailedge.master_experience.get_retailedge_business_hub_context", component)

	def test_operating_context_keeps_server_authority(self):
		component = EDGE_SUITE_REQUIRED_PAGES["operating_context"]["component"].read_text(encoding="utf-8")
		self.assertIn("retailedge.operating_context.get_allowed_operating_contexts", component)
		self.assertIn("retailedge.operating_context.switch_operating_context", component)
		self.assertIn("retailedge.operating_context.clear_operating_context", component)
		self.assertIn("retailedgeOperatingContextGuard", component)
		self.assertNotIn("frappe.db.set_value", component)
		self.assertNotIn("frappe.client.save", component)


if __name__ == "__main__":
	unittest.main()
