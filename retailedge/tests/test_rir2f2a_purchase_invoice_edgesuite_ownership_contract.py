from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.master_experience import (
	PURCHASE_INVOICE_NATIVE_PEER_DOCTYPE,
	PURCHASE_REGISTER_PAGE_TARGET,
	_promote_purchase_invoice_ownership,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestRIR2F2APurchaseInvoiceEdgeSuiteOwnershipContract(unittest.TestCase):
	def test_purchase_register_removes_native_purchase_invoice_peer_when_available(self):
		groups = [
			{
				"key": "buy",
				"items": [
					{"label": "Purchase Invoices", "target_type": "DocType", "target": "Purchase Invoice"},
					{"label": "Purchase Register", "target_type": "Page", "target": "purchase-register"},
					{"label": "Purchase Orders", "target_type": "DocType", "target": "Purchase Order"},
					{"label": "Purchase Receipts", "target_type": "DocType", "target": "Purchase Receipt"},
				],
			}
		]
		with patch("retailedge.master_experience._can_open_page", return_value=True):
			_promote_purchase_invoice_ownership(groups)

		targets = [item["target"] for item in groups[0]["items"]]
		self.assertNotIn(PURCHASE_INVOICE_NATIVE_PEER_DOCTYPE, targets)
		self.assertIn(PURCHASE_REGISTER_PAGE_TARGET, targets)
		self.assertIn("Purchase Order", targets)
		self.assertIn("Purchase Receipt", targets)

	def test_native_purchase_invoice_peer_remains_when_purchase_register_is_not_permitted(self):
		groups = [
			{
				"key": "buy",
				"items": [
					{"label": "Purchase Invoices", "target_type": "DocType", "target": "Purchase Invoice"},
					{"label": "Purchase Register", "target_type": "Page", "target": "purchase-register"},
				],
			}
		]
		with patch("retailedge.master_experience._can_open_page", return_value=False):
			_promote_purchase_invoice_ownership(groups)
		self.assertIn(PURCHASE_INVOICE_NATIVE_PEER_DOCTYPE, [item["target"] for item in groups[0]["items"]])

	def test_native_purchase_invoice_peer_remains_when_register_is_missing_from_composition(self):
		groups = [
			{
				"key": "buy",
				"items": [
					{"label": "Purchase Invoices", "target_type": "DocType", "target": "Purchase Invoice"},
					{"label": "Purchase Orders", "target_type": "DocType", "target": "Purchase Order"},
				],
			}
		]
		with patch("retailedge.master_experience._can_open_page", return_value=True):
			_promote_purchase_invoice_ownership(groups)
		self.assertIn(PURCHASE_INVOICE_NATIVE_PEER_DOCTYPE, [item["target"] for item in groups[0]["items"]])

	def test_transaction_workspace_keeps_purchase_invoice_create_and_read_inside_edgesuite(self):
		source = (APP_ROOT / "public/js/transaction_workspace/TransactionWorkspace.vue").read_text(encoding="utf-8")
		self.assertIn('if (action.doctype === "Purchase Invoice")', source)
		self.assertIn("this.simplePurchaseInvoiceOpen = true", source)
		self.assertIn('frappe.set_route("purchase-register")', source)
		self.assertIn(':nativeFallbackEnabled="false"', source)
		self.assertNotIn("openNativePurchaseInvoice", source)

	def test_purchase_invoice_native_escape_is_explicitly_advanced_when_enabled_elsewhere(self):
		source = (APP_ROOT / "public/js/retailedge_business_hub/SimplePurchaseInvoiceDialog.vue").read_text(encoding="utf-8")
		self.assertIn("Advanced: Open in ERPNext", source)
		self.assertIn("if (this.saving || !this.nativeFallbackEnabled) return;", source)
		self.assertNotIn("Open Full Form", source)


if __name__ == "__main__":
	unittest.main()
