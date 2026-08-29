from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.guided_stock_adjustment import _normalise_items

APP_ROOT = Path(__file__).resolve().parents[1]
HUB_ROOT = APP_ROOT / "public" / "js" / "retailedge_business_hub"


class TestGuidedStockAdjustment(unittest.TestCase):
	def test_physical_zero_quantity_is_valid(self):
		rows = _normalise_items([{"item_code": "ITEM-001", "qty": 0}])
		self.assertEqual(rows, [{"item_code": "ITEM-001", "qty": 0.0}])

	def test_negative_physical_quantity_is_blocked(self):
		with self.assertRaises(Exception):
			_normalise_items([{"item_code": "ITEM-001", "qty": -1}])

	def test_duplicate_item_is_blocked(self):
		with self.assertRaises(Exception):
			_normalise_items(
				[
					{"item_code": "ITEM-001", "qty": 3},
					{"item_code": "ITEM-001", "qty": 4},
				]
			)

	def test_backend_is_stock_reconciliation_draft_and_hides_valuation(self):
		source = (APP_ROOT / "guided_stock_adjustment.py").read_text(encoding="utf-8")
		self.assertIn('STOCK_RECONCILIATION_DOCTYPE = "Stock Reconciliation"', source)
		self.assertIn('doc.purpose = STOCK_RECONCILIATION_PURPOSE', source)
		self.assertIn('doc.insert()', source)
		self.assertNotIn('doc.submit()', source)
		self.assertNotIn('"valuation_rate": item', source)
		self.assertNotIn('current_valuation_rate', source)
		self.assertNotIn('current_amount', source)
		self.assertIn('"valuation_hidden": True', source)
		self.assertIn('frappe.has_permission(', source)
		self.assertIn('STOCK_RECONCILIATION_DOCTYPE, "create"', source)

	def test_backend_uses_bounded_permission_aware_searches(self):
		source = (APP_ROOT / "guided_stock_adjustment.py").read_text(encoding="utf-8")
		self.assertIn("MAX_LINK_RESULTS = 20", source)
		self.assertIn("MAX_ITEMS = 50", source)
		self.assertIn("validate_user_branch_access", source)
		self.assertIn("_validate_branch_warehouse", source)
		self.assertIn('reference_doctype="Stock Reconciliation Item"', source)
		self.assertIn('reference_doctype=STOCK_RECONCILIATION_DOCTYPE', source)

	def test_dialog_never_exposes_cost_or_valuation_fields(self):
		source = (HUB_ROOT / "SimpleStockAdjustmentDialog.vue").read_text(encoding="utf-8")
		self.assertIn("Physical Qty", source)
		self.assertIn("Valuation and cost fields are deliberately not exposed", source)
		self.assertNotIn('fieldname: "valuation_rate"', source)
		self.assertNotIn('fieldname: "current_valuation_rate"', source)
		self.assertNotIn('fieldname: "amount"', source)
		self.assertIn('this.$emit("open-native", "Stock Reconciliation")', source)


if __name__ == "__main__":
	unittest.main()
