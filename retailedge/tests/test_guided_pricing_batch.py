from __future__ import annotations

import unittest
from pathlib import Path

import frappe

from retailedge.guided_pricing_api import _normalise_pricing_rows

APP_ROOT = Path(__file__).resolve().parents[1]


class TestGuidedPricingBatch(unittest.TestCase):
	def test_batch_rows_are_bounded_and_keep_client_index(self):
		rows = _normalise_pricing_rows(
			[
				{"index": 7, "item_code": "ITEM-001", "qty": 2},
				{"index": 3, "item_code": "ITEM-002", "qty": "4"},
			],
			max_items=50,
		)
		self.assertEqual(rows[0], {"index": 7, "item_code": "ITEM-001", "qty": 2.0})
		self.assertEqual(rows[1], {"index": 3, "item_code": "ITEM-002", "qty": 4.0})

	def test_batch_rejects_oversized_or_invalid_quantity(self):
		with self.assertRaises(frappe.ValidationError):
			_normalise_pricing_rows([{"item_code": "ITEM", "qty": 1}] * 51, max_items=50)
		with self.assertRaises(frappe.ValidationError):
			_normalise_pricing_rows([{"item_code": "ITEM", "qty": 0}], max_items=50)

	def test_batch_api_reuses_guided_permissions_and_server_pricing(self):
		source = (APP_ROOT / "guided_pricing_api.py").read_text(encoding="utf-8")
		for contract in (
			"get_sales_item_pricing_batch",
			"get_purchase_item_pricing_batch",
			"_assert_can_create_sales_invoice",
			"_assert_can_create_purchase_invoice",
			"_validate_sales_context",
			"_validate_purchase_context",
			"resolve_sales_item_pricing",
			"resolve_purchase_item_pricing",
			"SALES_MAX_ITEMS",
			"PURCHASE_MAX_ITEMS",
		):
			self.assertIn(contract, source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.get_all(", source)
		self.assertNotIn("frappe.db.commit()", source)


if __name__ == "__main__":
	unittest.main()
