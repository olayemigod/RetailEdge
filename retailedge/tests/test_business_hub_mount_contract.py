from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeBusinessHubMountContractTests(unittest.TestCase):
	def test_business_hub_mounts_created_edge_app_into_resolved_target(self):
		bundle = (APP_ROOT / "public" / "js" / "retailedge_business_hub.bundle.js").read_text()

		self.assertIn("const app = window.EdgeSuiteUI.createEdgeApp(RetailEdgeBusinessHub);", bundle)
		self.assertIn("target.append(readinessTarget, hubTarget);", bundle)
		self.assertIn("readinessApp.mount(readinessTarget);", bundle)
		self.assertIn("app.mount(hubTarget);", bundle)
		self.assertIn("readinessApp.unmount();", bundle)
		self.assertIn("originalUnmount();", bundle)
		self.assertIn("return app;", bundle)
		self.assertNotIn("createEdgeApp(RetailEdgeBusinessHub, target)", bundle)

	def test_business_hub_rebinds_shared_components_at_mount_time(self):
		bundle = (APP_ROOT / "public" / "js" / "retailedge_business_hub.bundle.js").read_text()

		bind_index = bundle.index("const missingComponents = bindEdgeSuiteRuntimeComponents(")
		mount_index = bundle.index("const readinessApp = window.EdgeSuiteUI.createEdgeApp(UserReadinessNotice);")
		self.assertLess(bind_index, mount_index)
		self.assertIn("rootComponents.forEach(visit);", bundle)
		self.assertIn("visit(registeredComponent);", bundle)
		self.assertIn("if (registeredComponent == null)", bundle)
		self.assertIn("localComponents[name] = runtimeComponent;", bundle)
		self.assertIn("window.EdgeSuiteUI.components || window.EdgeSuiteUI", bundle)
		self.assertIn("if (missingComponents.length)", bundle)
		self.assertIn("required interface components are unavailable", bundle)


if __name__ == "__main__":
	unittest.main()
