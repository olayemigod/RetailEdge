from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from retailedge.managed_review_reports import SURFACES
from retailedge.navigation_consolidation import (
	LEGACY_SHIFT_REVIEW_TARGETS,
	PRESERVED_SHIFT_WORKFLOW_TARGETS,
	SHIFT_RECONCILIATION_TARGET,
	_consolidate_shift_review_navigation,
)


APP_ROOT = Path(__file__).resolve().parents[1]


class TestShiftReconciliationConsolidation(unittest.TestCase):
	def test_duplicate_read_surfaces_collapse_into_shift_reconciliation(self):
		groups = [
			{
				"key": "review-approvals",
				"label": "Review & Approvals",
				"items": [
					{"label": "Action Centre", "target_type": "Page", "target": "action-center", "icon": "bell"},
					{"label": "Daily Sales Audit", "target_type": "Page", "target": "daily-sales-audit", "icon": "shield"},
					{"label": "Cashier Expense Review", "target_type": "Page", "target": "expense-review", "icon": "report"},
					{"label": "Cash Shift Verification", "target_type": "Page", "target": "cash-shift-verification", "icon": "report"},
					{"label": "POS Closing Variance & Expenses", "target_type": "Page", "target": "pos-closing-variance", "icon": "report"},
					{"label": "Daily Sales Audit Register", "target_type": "Page", "target": "daily-sales-audit-register", "icon": "report"},
					{"label": "Banking Readiness", "target_type": "Page", "target": "banking-readiness", "icon": "shield"},
				],
			}
		]

		_consolidate_shift_review_navigation(groups)

		items = groups[0]["items"]
		shift_read_items = [
			item
			for item in items
			if item.get("target") in LEGACY_SHIFT_REVIEW_TARGETS | {SHIFT_RECONCILIATION_TARGET}
		]
		self.assertEqual(len(shift_read_items), 1)
		self.assertEqual(shift_read_items[0]["target"], SHIFT_RECONCILIATION_TARGET)
		self.assertEqual(shift_read_items[0]["label"], "Shift Reconciliation")
		self.assertEqual(shift_read_items[0]["icon"], "check-circle")
		self.assertEqual(items[0]["target"], "action-center")
		self.assertEqual(items[1]["target"], SHIFT_RECONCILIATION_TARGET)
		self.assertTrue(any(item.get("target") == "banking-readiness" for item in items))

	def test_mutating_review_workflows_remain_visible_until_absorbed(self):
		groups = [
			{
				"key": "review-approvals",
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

		targets = {item.get("target") for item in groups[0]["items"]}
		self.assertTrue(PRESERVED_SHIFT_WORKFLOW_TARGETS.issubset(targets))
		self.assertNotIn("cash-shift-verification", targets)

	def test_navigation_is_preserved_when_user_cannot_open_canonical_page(self):
		groups = [
			{
				"key": "review-approvals",
				"items": [
					{"label": "Daily Sales Audit", "target_type": "Page", "target": "daily-sales-audit"},
					{"label": "Cash Shift Verification", "target_type": "Page", "target": "cash-shift-verification"},
				],
			}
		]
		original = deepcopy(groups)

		_consolidate_shift_review_navigation(groups)

		self.assertEqual(groups, original)

	def test_shift_reconciliation_surface_uses_customer_facing_copy(self):
		surface = SURFACES[SHIFT_RECONCILIATION_TARGET]
		self.assertEqual(surface["title"], "Shift Reconciliation")
		self.assertEqual(surface["eyebrow"], "Cash Control")
		self.assertEqual(
			surface["action"],
			{"label": "Detailed Shift Audit", "route": "cash-shift-verification"},
		)
		self.assertIn("cashier expenses", surface["subtitle"].lower())
		self.assertIn("deposits", surface["subtitle"].lower())

	def test_both_business_hub_rpc_paths_use_final_consolidated_context(self):
		hooks = (APP_ROOT / "hooks.py").read_text()
		target = "retailedge.navigation_consolidation.get_retailedge_business_hub_context"
		self.assertIn(
			f'"retailedge.edgesuite_ui.get_retailedge_business_hub_context": "{target}"',
			hooks,
		)
		self.assertIn(
			f'"retailedge.master_experience.get_retailedge_business_hub_context": "{target}"',
			hooks,
		)

	def test_pos_closing_page_uses_shift_reconciliation_title(self):
		page_directory = APP_ROOT / "retailedge" / "page" / "pos_closing_variance"
		page_js = (page_directory / "pos_closing_variance.js").read_text()
		page_json = json.loads((page_directory / "pos_closing_variance.json").read_text())
		self.assertIn('const PAGE_TITLE = "Shift Reconciliation";', page_js)
		self.assertNotIn('const PAGE_TITLE = "POS Closing Variance & Expenses";', page_js)
		self.assertEqual(page_json["title"], "Shift Reconciliation")


if __name__ == "__main__":
	unittest.main()
