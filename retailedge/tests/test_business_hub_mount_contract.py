from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeBusinessHubMountContractTests(unittest.TestCase):
	def test_business_hub_mounts_created_edge_app_into_resolved_target(self):
		bundle = (APP_ROOT / "public" / "js" / "retailedge_business_hub.bundle.js").read_text()

		self.assertIn("const app = window.EdgeSuiteUI.createEdgeApp(RetailEdgeBusinessHub);", bundle)
		self.assertIn("app.mount(target);", bundle)
		self.assertIn("return app;", bundle)
		self.assertNotIn("createEdgeApp(RetailEdgeBusinessHub, target)", bundle)


if __name__ == "__main__":
	unittest.main()
