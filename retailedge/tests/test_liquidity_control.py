from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.liquidity_control import _build_liquidity_control

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeLiquidityControlTests(unittest.TestCase):
	def test_liquidity_distinguishes_balance_due_items_and_period_flow(self):
		position = {
			"current_position": [
				{"label": "Cash & Bank Balance", "value": 5000, "available": True},
			],
			"selected_period": [
				{"label": "Money In", "value": 12000, "available": True},
				{"label": "Money Out", "value": 9000, "available": True},
				{"label": "Net Cash Movement", "value": 3000, "available": True},
			],
		}
		receivables = {
			"rows": [
				{"invoice": "SINV-1", "due_date": "2026-08-01", "outstanding": 2000, "overdue_days": 21},
				{"invoice": "SINV-2", "due_date": "2026-09-10", "outstanding": 1000, "overdue_days": 0},
			],
			"scan": {"invoice_limit": 2000},
		}
		payables = {
			"rows": [
				{"invoice": "PINV-1", "due_date": "2026-08-15", "outstanding": 2500, "overdue_days": 7},
				{"invoice": "PINV-2", "due_date": "2026-10-15", "outstanding": 4000, "overdue_days": 0},
			],
			"scan": {"invoice_limit": 2000},
		}

		result = _build_liquidity_control(position, receivables, payables, horizon_days=30)
		current = result["current_liquidity"]
		self.assertEqual(current["cash_bank_balance"], 5000)
		self.assertEqual(current["supplier_obligations_due_within_horizon"], 2500)
		self.assertEqual(current["receivables_due_within_horizon"], 3000)
		self.assertEqual(current["immediate_obligation_coverage_ratio"], 2.0)
		self.assertEqual(current["indicative_coverage_ratio_including_due_receivables"], 3.2)
		self.assertEqual(result["period_flow"]["net_cash_movement"], 3000)

	def test_branch_without_safe_cash_balance_withholds_cash_ratios(self):
		position = {
			"current_position": [
				{"label": "Cash & Bank Balance", "value": None, "available": False, "reason": "Branch balance unavailable"},
			],
			"selected_period": [],
		}
		result = _build_liquidity_control(position, {"rows": []}, {"rows": [{"due_date": "2026-08-01", "outstanding": 1000, "overdue_days": 20}]}, horizon_days=30)
		current = result["current_liquidity"]
		self.assertFalse(current["cash_bank_available"])
		self.assertIsNone(current["immediate_obligation_coverage_ratio"])
		self.assertIsNone(current["indicative_liquidity_gap"])

	def test_service_reuses_existing_truth_engines_without_full_owner_dashboard_reload(self):
		source = (APP_ROOT / "liquidity_control.py").read_text()
		self.assertIn("_get_liquid_position", source)
		self.assertIn("get_cash_movement", source)
		self.assertIn("get_customer_receivables_export", source)
		self.assertIn("get_supplier_payables_export", source)
		self.assertIn("require_dashboard_action", source)
		self.assertNotIn("get_owner_dashboard_data", source)
		self.assertNotIn("get_financial_position", source)
		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertIn("not a cash forecast", source)
		self.assertIn("withheld rather than inferred", source)
		self.assertIn("no full Owner Dashboard reload", source)


if __name__ == "__main__":
	unittest.main()
