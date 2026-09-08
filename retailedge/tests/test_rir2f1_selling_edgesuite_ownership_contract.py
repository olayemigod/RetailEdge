from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.master_experience import (
	PROFESSIONAL_SELLING_ITEM,
	SELLING_NATIVE_PEER_DOCTYPES,
	_promote_professional_selling,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class RIR2F1SellingEdgeSuiteOwnershipContractTests(unittest.TestCase):
	def _sell_group(self):
		return [
			{
				"key": "sell",
				"items": [
					{"label": "Transaction Workspace", "target_type": "Page", "target": "transaction-workspace"},
					{"label": "Start POS", "target_type": "URL", "target": "/pos", "runtime_target": "pos"},
					{"label": "Sales Invoices", "target_type": "DocType", "target": "Sales Invoice"},
					{"label": "Sales Orders", "target_type": "DocType", "target": "Sales Order"},
					{"label": "Delivery Notes", "target_type": "DocType", "target": "Delivery Note"},
					{"label": "Sales Team & Targets", "target_type": "Page", "target": "sales-team-control"},
				],
			}
		]

	def test_professional_selling_replaces_native_everyday_peers_when_page_is_permitted(self):
		groups = self._sell_group()
		with patch("retailedge.master_experience._can_open_page", return_value=True):
			_promote_professional_selling(groups)

		items = groups[0]["items"]
		targets = [item["target"] for item in items]
		self.assertIn(PROFESSIONAL_SELLING_ITEM["target"], targets)
		self.assertTrue(SELLING_NATIVE_PEER_DOCTYPES.isdisjoint(targets))
		self.assertIn("transaction-workspace", targets)
		self.assertIn("/pos", targets)
		self.assertIn("sales-team-control", targets)
		self.assertLess(targets.index("transaction-workspace"), targets.index(PROFESSIONAL_SELLING_ITEM["target"]))

	def test_existing_professional_selling_page_is_deduplicated_while_native_peers_are_removed(self):
		groups = self._sell_group()
		groups[0]["items"].insert(1, dict(PROFESSIONAL_SELLING_ITEM))
		with patch("retailedge.master_experience._can_open_page", return_value=True):
			_promote_professional_selling(groups)

		targets = [item["target"] for item in groups[0]["items"]]
		self.assertEqual(targets.count(PROFESSIONAL_SELLING_ITEM["target"]), 1)
		self.assertTrue(SELLING_NATIVE_PEER_DOCTYPES.isdisjoint(targets))

	def test_native_peer_fallback_remains_when_professional_selling_is_not_permitted(self):
		groups = self._sell_group()
		before = [dict(item) for item in groups[0]["items"]]
		with patch("retailedge.master_experience._can_open_page", return_value=False):
			_promote_professional_selling(groups)
		self.assertEqual(groups[0]["items"], before)

	def test_professional_selling_frontend_is_edgesuite_first(self):
		source = (APP_ROOT / "public" / "js" / "professional_selling" / "ProfessionalSelling.vue").read_text()
		self.assertNotIn('@click="openNative(document)">View Records', source)
		self.assertNotIn('@click="openRecord(recentDocument, row.name)"', source)
		self.assertNotIn("if (result?.route) window.open(result.route", source)
		self.assertIn("canUseNativeDesk", source)
		self.assertIn("navigation.access?.can_use_native_desk", source)
		self.assertIn("Advanced: Open in ERPNext", source)
		self.assertIn("openAdvancedNative(document)", source)
		self.assertIn("openAdvancedRecord(recentDocument, row.name)", source)
		self.assertIn(":deep(.selling-form-footer > .edge-button:first-child)", source)

	def test_transaction_workspace_sales_invoice_read_path_uses_professional_selling_only(self):
		source = (APP_ROOT / "public" / "js" / "transaction_workspace" / "TransactionWorkspace.vue").read_text()
		self.assertIn('@click="viewTransactionRecords(action)"', source)
		self.assertIn('if (action?.doctype === "Sales Invoice")', source)
		self.assertIn('frappe.set_route("professional-selling")', source)
		self.assertNotIn("openNativeSalesInvoice", source)
		self.assertIn("openNativeStockTransfer", source)
		self.assertIn('this.openDoctype(action?.doctype)', source)

	def test_professional_selling_feature_flag_declares_primary_ownership(self):
		source = (APP_ROOT / "master_experience.py").read_text()
		self.assertIn('feature_flags["professional_selling"] = "edgesuite_primary"', source)


if __name__ == "__main__":
	unittest.main()
