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
				"record-expense",
				"record-purchase",
				"transfer-stock",
			],
		)
		self.assertTrue(all(action.get("doctype") for action in QUICK_ACTIONS))
		self.assertTrue(
			all(action.get("mode") in {"available", "native_fallback"} for action in QUICK_ACTIONS)
		)

	def test_business_hub_exposes_one_create_picker_not_duplicate_action_grid(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "RetailEdgeBusinessHub.vue"
		).read_text()

		self.assertIn("+ Create", component)
		self.assertIn("EdgeModal: runtimeComponents.EdgeModal", component)
		self.assertIn(':open="createPickerOpen"', component)
		self.assertIn('title="Create"', component)
		self.assertIn("openCreatePicker()", component)
		self.assertIn("closeCreatePicker()", component)
		self.assertIn("v-for=\"action in quickActions\"", component)
		self.assertIn("frappe.new_doc(action.doctype)", component)
		self.assertNotIn("quick-action-grid", component)

	def test_create_picker_routes_only_sales_invoice_to_guided_adapter(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "RetailEdgeBusinessHub.vue"
		).read_text()

		self.assertIn('if (action.key === "new-sales-invoice")', component)
		self.assertIn("this.simpleSalesInvoiceOpen = true", component)
		self.assertIn("SimpleSalesInvoiceDialog", component)
		self.assertIn('if (action?.key === "new-sales-invoice") return "RetailEdge entry";', component)
		self.assertIn('return action?.mode === "available" ? "RetailEdge entry" : "Full form";', component)
		self.assertIn("this.closeCreatePicker();", component)
		self.assertNotIn("frappe.client.insert", component)
		self.assertNotIn("frappe.db.insert", component)


if __name__ == "__main__":
	unittest.main()
