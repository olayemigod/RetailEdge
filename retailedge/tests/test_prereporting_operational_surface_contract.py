from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.master_experience import (
	PAYMENT_MANAGEMENT_ITEM,
	PROFESSIONAL_PURCHASING_ITEM,
	PROFESSIONAL_SELLING_ITEM,
	PROMOTED_R4_PAGE_TARGETS,
	_promote_browser_approved_r4_pages,
	_promote_payment_management,
	_promote_professional_purchasing,
	_promote_professional_selling,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgePreReportingOperationalSurfaceContractTests(unittest.TestCase):
	def test_professional_selling_is_promoted_when_page_is_permitted(self):
		groups = [{"key": "sell", "items": [{"label": "Sales Invoices", "target_type": "DocType", "target": "Sales Invoice"}]}]
		with patch("retailedge.master_experience._can_open_page", return_value=True):
			_promote_professional_selling(groups)

		self.assertEqual(groups[0]["items"][0]["target_type"], "Page")
		self.assertEqual(groups[0]["items"][0]["target"], PROFESSIONAL_SELLING_ITEM["target"])

	def test_professional_purchasing_is_promoted_before_native_purchase_order(self):
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
			_promote_professional_purchasing(groups)

		targets = [item["target"] for item in groups[0]["items"]]
		self.assertLess(targets.index(PROFESSIONAL_PURCHASING_ITEM["target"]), targets.index("Purchase Order"))

	def test_payment_management_is_promoted_before_native_payment_entry(self):
		groups = [
			{
				"key": "money",
				"items": [
					{"label": "Cash Movement", "target_type": "Page", "target": "cash-movement"},
					{"label": "Payments", "target_type": "DocType", "target": "Payment Entry"},
				],
			}
		]
		with (
			patch("retailedge.master_experience._can_open_page", return_value=True),
			patch("retailedge.master_experience._can_open_report", return_value=False),
		):
			_promote_payment_management(groups)

		targets = [item["target"] for item in groups[0]["items"]]
		self.assertLess(targets.index(PAYMENT_MANAGEMENT_ITEM["target"]), targets.index("Payment Entry"))

	def test_stock_movement_history_remains_on_legacy_report_until_its_parity_gate(self):
		groups = [
			{
				"key": "stock",
				"items": [
					{
						"label": "Stock Movement History",
						"target_type": "Report",
						"target": "RetailEdge Stock Movement History",
					}
				],
			}
		]

		_promote_browser_approved_r4_pages(groups)

		self.assertNotIn("Stock Movement History", PROMOTED_R4_PAGE_TARGETS)
		self.assertEqual(groups[0]["items"][0]["target_type"], "Report")
		self.assertEqual(groups[0]["items"][0]["target"], "RetailEdge Stock Movement History")

	def test_promoted_pages_are_standard_and_role_restricted(self):
		page_paths = {
			"professional-selling": APP_ROOT / "retailedge" / "page" / "professional_selling" / "professional_selling.json",
			"professional-purchasing": APP_ROOT / "retailedge" / "page" / "professional_purchasing" / "professional_purchasing.json",
			"payment-management": APP_ROOT / "retailedge" / "page" / "payment_management" / "payment_management.json",
		}
		for page_name, path in page_paths.items():
			with self.subTest(page=page_name):
				data = json.loads(path.read_text())
				self.assertEqual(data["name"], page_name)
				self.assertEqual(data["standard"], "Yes")
				self.assertTrue(data.get("roles"))

	def test_purchasing_page_does_not_broaden_purchase_authority_to_product_roles(self):
		path = APP_ROOT / "retailedge" / "page" / "professional_purchasing" / "professional_purchasing.json"
		roles = {row["role"] for row in json.loads(path.read_text())["roles"]}
		self.assertTrue({"Purchase User", "Purchase Manager"}.intersection(roles))
		self.assertNotIn("RetailEdge Manager", roles)
		self.assertNotIn("RetailEdgeManager", roles)
		self.assertNotIn("RetailEdge Branch Manager", roles)
		self.assertNotIn("RetailEdgeBranchManager", roles)


if __name__ == "__main__":
	unittest.main()
