from __future__ import annotations

import unittest

from retailedge.sales_commercial_preview import _preview_item_rows
from retailedge.sales_item_discounts import MANUAL_DISCOUNT_PERCENTAGE


class TestSalesCommercialPreviewBlankRows(unittest.TestCase):
	def test_live_preview_ignores_new_blank_child_rows_without_dropping_discount_input(self):
		rows = _preview_item_rows(
			[
				{
					"item_code": "SOLAR-GEN",
					"qty": 1,
					"rate": 23000,
					MANUAL_DISCOUNT_PERCENTAGE: 10,
				},
				{"item_code": "", "qty": 1, "rate": ""},
				{"qty": 1},
			]
		)

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["item_code"], "SOLAR-GEN")
		self.assertEqual(rows[0][MANUAL_DISCOUNT_PERCENTAGE], 10)

	def test_live_preview_preserves_malformed_non_dict_rows_for_normal_validation(self):
		rows = _preview_item_rows([{"item_code": ""}, "invalid-row"])
		self.assertEqual(rows, ["invalid-row"])

	def test_live_preview_accepts_json_child_rows(self):
		rows = _preview_item_rows('[{"item_code":"ITEM-001","qty":1},{"item_code":"","qty":1}]')
		self.assertEqual(rows, [{"item_code": "ITEM-001", "qty": 1}])


if __name__ == "__main__":
	unittest.main()
