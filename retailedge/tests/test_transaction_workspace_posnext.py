from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestTransactionWorkspacePOSNext(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_sell_navigation_adds_transaction_workspace_without_removing_direct_pos(self):
		source = self.read("master_experience.py")
		for contract in (
			"TRANSACTION_WORKSPACE_ITEM",
			"_promote_transaction_workspace",
			'"target": "transaction-workspace"',
			'item.get("runtime_target") == "pos"',
			'_can_open_page(TRANSACTION_WORKSPACE_ITEM["target"])',
			'feature_flags["transaction_workspace"] = "edgesuite_host"',
			"existing provider-aware Start POS item remains available",
			"items.insert(pos_index, deepcopy(TRANSACTION_WORKSPACE_ITEM))",
		):
			self.assertIn(contract, source)
		self.assertNotIn("items[index] = deepcopy(TRANSACTION_WORKSPACE_ITEM)", source)

	def test_workspace_backend_reuses_operating_context_and_runtime_provider(self):
		source = self.read("retailedge/page/transaction_workspace/transaction_workspace.py")
		for contract in (
			"get_operating_context",
			"get_pos_runtime_capabilities",
			"frappe.has_permission",
			'"default_pos_profile"',
			'"default_stock_location"',
			'"embedded": False',
		):
			self.assertIn(contract, source)
		for forbidden in (
			"ignore_permissions=True",
			"frappe.db.commit",
			'frappe.new_doc("Sales Invoice")',
			'frappe.new_doc("Stock Entry")',
			"submit()",
		):
			self.assertNotIn(forbidden, source)

	def test_pos_launch_is_server_validated_and_read_only(self):
		backend = self.read("retailedge/page/transaction_workspace/transaction_workspace.py")
		component = self.read("public/js/transaction_workspace/TransactionWorkspace.vue")
		for contract in (
			"def prepare_pos_launch()",
			"find_open_pos_opening_shift",
			"resolve_branch_from_opening_shift",
			"resolve_branch_from_pos_profile",
			"Choose an Operating Company and Branch before starting POS.",
			"active POS shift does not match the current Operating Branch",
			"active POS shift uses a different POS Profile",
		):
			self.assertIn(contract, backend)
		for forbidden in (
			".save()",
			".insert()",
			".submit()",
			"frappe.db.set_value",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, backend)
		self.assertIn("POS_LAUNCH_METHOD", component)
		self.assertIn("await callMethod(POS_LAUNCH_METHOD)", component)
		self.assertIn("posLaunchError", component)

	def test_native_erpnext_pos_uses_permission_aware_online_parity_gate(self):
		backend = self.read("retailedge/page/transaction_workspace/transaction_workspace.py")
		for contract in (
			"def _find_open_erpnext_pos_opening",
			'frappe.get_list(',
			'"POS Opening Entry"',
			"active ERPNext POS opening belongs to another Company",
			"active ERPNext POS opening uses a different POS Profile",
			"_validate_pos_profile(entry_profile, company=company, branch=branch)",
		):
			self.assertIn(contract, backend)
		self.assertNotIn('frappe.get_all(\n\t\t\t"POS Opening Entry"', backend)

	def test_posnext_offline_launch_does_not_depend_on_server_preflight(self):
		component = self.read("public/js/transaction_workspace/TransactionWorkspace.vue")
		for contract in (
			'if (this.pos?.provider === "posnext" && typeof navigator !== "undefined" && navigator.onLine === false)',
			"this.launchPosTarget(this.pos)",
			"window.location.assign(launch.start_url)",
			"RetailEdge does not make its preflight a hard dependency",
			"POSNext keeps control of its own offline runtime and sync behaviour",
		):
			self.assertIn(contract, component)
		self.assertIn('this.pos?.provider === "posnext"', component)

	def test_workspace_keeps_posnext_extension_boundary(self):
		component = self.read("public/js/transaction_workspace/TransactionWorkspace.vue")
		self.assertIn("POSNext remains the POS engine", component)
		self.assertIn("ProcessEdge POSNext extension", component)
		self.assertNotIn("safe context handoff", component)
		self.assertNotIn("allow_user_to_edit_rate", component)
		self.assertNotIn("allow_change_posting_date", component)
		self.assertNotIn("posting_date", component)
		self.assertNotIn("<iframe", component.lower())

	def test_workspace_reuses_existing_guided_transaction_components(self):
		component = self.read("public/js/transaction_workspace/TransactionWorkspace.vue")
		for contract in (
			'../retailedge_business_hub/SimpleSalesInvoiceDialog.vue',
			'../retailedge_business_hub/SimplePurchaseInvoiceDialog.vue',
			'../retailedge_business_hub/SimpleStockTransferDialog.vue',
			"SimpleSalesInvoiceDialog",
			"SimplePurchaseInvoiceDialog",
			"SimpleStockTransferDialog",
			"runTransactionAction(action)",
			'GUIDED_DOCTYPES = new Set(["Sales Invoice", "Purchase Invoice", "Stock Entry"])',
		):
			self.assertIn(contract, component)

	def test_native_transaction_fallbacks_remain_authoritative(self):
		component = self.read("public/js/transaction_workspace/TransactionWorkspace.vue")
		self.assertIn("createDoctype(action.doctype)", component)
		self.assertIn("openDoctype(action.doctype)", component)
		self.assertIn("window.open(`/app/${doctypeSlug(doctype)}/new`", component)
		self.assertNotIn("frappe.client.insert", component)
		self.assertNotIn("frappe.client.save", component)


if __name__ == "__main__":
	unittest.main()
