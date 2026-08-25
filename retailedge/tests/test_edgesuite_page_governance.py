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
		"asset": "operating_context.bundle.js",
		"mount": "mountRetailEdgeOperatingContext",
		"component_name": "OperatingContext.vue",
	},
	"retailedge_setup": {
		"loader": APP_ROOT / "retailedge" / "page" / "retailedge_setup" / "retailedge_setup.js",
		"bundle": APP_ROOT / "public" / "js" / "retailedge_setup.bundle.js",
		"component": APP_ROOT / "public" / "js" / "retailedge_setup" / "RetailEdgeSetup.vue",
		"asset": "retailedge_setup.bundle.js",
		"mount": "mountRetailEdgeSetup",
		"component_name": "RetailEdgeSetup.vue",
	},
	"transaction_workspace": {
		"loader": APP_ROOT / "retailedge" / "page" / "transaction_workspace" / "transaction_workspace.js",
		"bundle": APP_ROOT / "public" / "js" / "transaction_workspace.bundle.js",
		"component": APP_ROOT / "public" / "js" / "transaction_workspace" / "TransactionWorkspace.vue",
		"asset": "transaction_workspace.bundle.js",
		"mount": "mountRetailEdgeTransactionWorkspace",
		"component_name": "TransactionWorkspace.vue",
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
				self.assertIn(f'"{files["asset"]}"', loader)
				self.assertIn("window.EdgeSuiteUI", loader)
				self.assertIn(files["mount"], loader)
				self.assertNotIn('className = "frappe-card"', loader)

				self.assertIn("createEdgeApp", bundle)
				self.assertIn(files["component_name"], bundle)
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

	def test_setup_page_uses_native_doctypes_as_authoritative_editors(self):
		component = EDGE_SUITE_REQUIRED_PAGES["retailedge_setup"]["component"].read_text(encoding="utf-8")
		backend = (APP_ROOT / "retailedge" / "page" / "retailedge_setup" / "retailedge_setup.py").read_text(encoding="utf-8")
		self.assertIn("get_setup_context", component)
		self.assertIn("window.open(`/app/${doctypeSlug(resource.doctype)}`", component)
		self.assertNotIn("frappe.client.save", component)
		self.assertNotIn("ignore_permissions", backend)
		self.assertIn("frappe.get_list", backend)
		self.assertNotIn("frappe.get_all", backend)

	def test_transaction_workspace_keeps_provider_and_document_truth_server_authoritative(self):
		component = EDGE_SUITE_REQUIRED_PAGES["transaction_workspace"]["component"].read_text(encoding="utf-8")
		backend = (APP_ROOT / "retailedge" / "page" / "transaction_workspace" / "transaction_workspace.py").read_text(encoding="utf-8")
		self.assertIn("get_transaction_workspace_context", component)
		self.assertIn("get_pos_runtime_capabilities", backend)
		self.assertIn("get_operating_context", backend)
		self.assertIn("frappe.has_permission", backend)
		self.assertNotIn("ignore_permissions", backend)
		self.assertNotIn("frappe.db.commit", backend)
		self.assertNotIn("frappe.client.save", component)
		self.assertNotIn("<iframe", component.lower())


if __name__ == "__main__":
	unittest.main()
