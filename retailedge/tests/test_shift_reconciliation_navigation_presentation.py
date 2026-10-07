from __future__ import annotations

import unittest

from retailedge.navigation_consolidation import (
	LEGACY_SHIFT_REVIEW_TARGETS,
	PRESERVED_SHIFT_WORKFLOW_TARGETS,
	SHIFT_RECONCILIATION_TARGET,
	_consolidate_shift_review_navigation,
)


class TestShiftReconciliationNavigationPresentation(unittest.TestCase):
	def test_final_operations_review_group_is_consolidated(self):
		groups = [
			{
				"key": "operations-review",
				"label": "Operations Review",
				"items": [
					{"label": "Action Centre", "target_type": "Page", "target": "action-center"},
					{"label": "Daily Sales Audit", "target_type": "Page", "target": "daily-sales-audit"},
					{"label": "Cashier Expense Review", "target_type": "Page", "target": "expense-review"},
					{"label": "Cash Shift Verification", "target_type": "Page", "target": "cash-shift-verification"},
					{"label": "POS Closing Variance & Expenses", "target_type": "Page", "target": "pos-closing-variance"},
				],
			}
		]

		_consolidate_shift_review_navigation(groups)

		items = groups[0]["items"]
		targets = {item.get("target") for item in items}
		self.assertTrue(PRESERVED_SHIFT_WORKFLOW_TARGETS.issubset(targets))
		self.assertTrue(LEGACY_SHIFT_REVIEW_TARGETS.isdisjoint(targets))
		self.assertIn(SHIFT_RECONCILIATION_TARGET, targets)
		self.assertEqual(items[1]["target"], SHIFT_RECONCILIATION_TARGET)
		self.assertEqual(items[1]["label"], "Shift Reconciliation")


if __name__ == "__main__":
	unittest.main()
