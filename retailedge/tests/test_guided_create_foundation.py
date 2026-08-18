from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.edgesuite_ui import QUICK_ACTIONS

APP_ROOT = Path(__file__).resolve().parents[1]


class TestGuidedCreateFoundation(unittest.TestCase):
	def test_create_action_registry_has_stable_unique_keys(self):
		keys = [action["key"] for action in QUICK_ACTIONS]
		self.assertEqual(len(keys), len(set(keys)))
		self.assertEqual(
			keys,
			[
				"new-sales-invoice",
				"receive-customer-payment",
				"pay-supplier",
				"cash-transfer",
				"record-expense",
				"record-purchase",
				"transfer-stock",
			],
		)
		self.assertTrue(all(action.get("doctype") for action in QUICK_ACTIONS))
		self.assertTrue(all(action.get("mode") == "available" for action in QUICK_ACTIONS))

	def test_business_hub_exposes_one_permission_filtered_create_picker(self):
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
		).read_text(encoding="utf-8")
		self.assertIn("+ Create", component)
		self.assertIn('v-if="quickActions.length"', component)
		self.assertIn("EdgeModal: runtimeComponents.EdgeModal", component)
		self.assertIn(':open="createPickerOpen"', component)
		self.assertIn('title="Create"', component)
		self.assertIn("openCreatePicker()", component)
		self.assertIn("closeCreatePicker()", component)
		self.assertIn('v-for="action in quickActions"', component)
		self.assertIn("frappe.new_doc(action.doctype)", component)
		self.assertNotIn("quick-action-grid", component)

	def test_create_picker_routes_all_registered_actions_to_guided_adapters(self):
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
		).read_text(encoding="utf-8")
		self.assertIn('if (action.key === "new-sales-invoice")', component)
		self.assertIn("this.simpleSalesInvoiceOpen = true", component)
		self.assertIn("SimpleSalesInvoiceDialog", component)
		self.assertIn('new Set(["receive-customer-payment", "pay-supplier"])', component)
		self.assertIn("GUIDED_PAYMENT_ACTIONS.has(action.key)", component)
		self.assertIn("this.simplePaymentOpen = true", component)
		self.assertIn("SimplePaymentDialog", component)
		self.assertIn('const GUIDED_CASH_TRANSFER_ACTION = "cash-transfer";', component)
		self.assertIn("action.key === GUIDED_CASH_TRANSFER_ACTION", component)
		self.assertIn("this.simpleCashTransferOpen = true", component)
		self.assertIn("SimpleCashTransferDialog", component)
		self.assertIn('const GUIDED_PURCHASE_ACTION = "record-purchase";', component)
		self.assertIn("this.simplePurchaseInvoiceOpen = true", component)
		self.assertIn("SimplePurchaseInvoiceDialog", component)
		self.assertIn('const GUIDED_EXPENSE_ACTION = "record-expense";', component)
		self.assertIn("this.simpleCashierExpenseOpen = true", component)
		self.assertIn("SimpleCashierExpenseDialog", component)
		self.assertIn('const GUIDED_STOCK_TRANSFER_ACTION = "transfer-stock";', component)
		self.assertIn("this.simpleStockTransferOpen = true", component)
		self.assertIn("SimpleStockTransferDialog", component)
		self.assertIn('return action?.mode === "available" ? "RetailEdge entry" : "Full form";', component)
		self.assertIn("this.closeCreatePicker();", component)
		self.assertNotIn("frappe.client.insert", component)
		self.assertNotIn("frappe.db.insert", component)

	def test_stock_and_cash_transfer_keep_explicit_full_form_fallbacks(self):
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
		).read_text(encoding="utf-8")
		self.assertIn("openNativeStockTransfer", component)
		self.assertIn('frappe.new_doc(doctype, { stock_entry_type: "Material Transfer" })', component)
		self.assertIn("openNativeCashTransfer", component)
		self.assertIn('frappe.new_doc(doctype, { payment_type: "Internal Transfer" })', component)


if __name__ == "__main__":
	unittest.main()
