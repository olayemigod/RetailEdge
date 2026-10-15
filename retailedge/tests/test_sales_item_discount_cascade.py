from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestSalesItemDiscountCascade(unittest.TestCase):
	def test_make_sale_item_change_clears_manual_discount_inputs(self):
		source = (
			APP_ROOT / "public" / "js" / "make_sale" / "commercialEditingExtension.js"
		).read_text(encoding="utf-8")

		self.assertIn(
			'if ((row?.item_code || "") !== (prior?.item_code || ""))',
			source,
		)
		self.assertIn("[MANUAL_PERCENTAGE]: 0", source)
		self.assertIn("[MANUAL_AMOUNT]: 0", source)
		self.assertIn('[MANUAL_MODE]: ""', source)
		self.assertIn('[MANUAL_VALUE]: ""', source)

	def test_quantity_change_does_not_clear_per_unit_discount_contract(self):
		source = (
			APP_ROOT / "public" / "js" / "make_sale" / "commercialEditingExtension.js"
		).read_text(encoding="utf-8")

		self.assertNotIn("row?.qty || 0) !== (prior?.qty", source)
		self.assertIn('const DISCOUNT_MODE_AMOUNT = "amount"', source)
		self.assertIn('label: "Amount / unit"', source)
		self.assertIn("[MANUAL_AMOUNT]: Number.isFinite(value) ? value : 0", source)


if __name__ == "__main__":
	unittest.main()
