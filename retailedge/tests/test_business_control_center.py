from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.business_control_center import _build_business_control_center

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeBusinessControlCenterTests(unittest.TestCase):
	def test_existing_action_items_and_net_new_r9_warnings_are_combined_without_duplicate_ar_ap(self):
		action_center = {
			"filters": {"company": "Demo Co", "branch": ""},
			"summary": [],
			"items": [
				{"source": "receivables", "semantic_key": "overdue_receivables", "label": "Customer receivables are overdue", "severity": "warning", "follow_up": {"is_due": False}},
				{"source": "payables", "semantic_key": "overdue_payables", "label": "Supplier payables are overdue", "severity": "warning", "follow_up": {"is_due": False}},
			],
			"sources": {},
			"metadata": {},
		}
		warnings = {
			"warnings": [
				{"severity": "warning", "family": "Collections", "label": "Overdue customer receivables require collection attention", "value": 1000, "datatype": "Currency", "route": "/app/customer-receivables"},
				{"severity": "warning", "family": "Supplier Obligations", "label": "Overdue supplier obligations require payment attention", "value": 800, "datatype": "Currency", "route": "/app/supplier-payables"},
				{"severity": "critical", "family": "Liquidity", "label": "Cash coverage is weak", "value": 0.7, "datatype": "Float", "route": "/app/supplier-payables"},
				{"severity": "warning", "family": "Profitability", "label": "Accounting net profit declined", "value": -30, "datatype": "Percent", "route": "/app/query-report/Profit%20and%20Loss%20Statement"},
			],
			"critical_count": 1,
			"warning_count": 3,
		}

		result = _build_business_control_center(action_center=action_center, warnings=warnings)
		self.assertEqual(len(result["items"]), 4)
		self.assertEqual(result["items"][0]["family"], "Liquidity")
		self.assertEqual(sum(1 for row in result["items"] if row.get("source") == "receivables"), 1)
		self.assertEqual(sum(1 for row in result["items"] if row.get("source") == "payables"), 1)
		r9 = [row for row in result["items"] if row.get("source") == "r9_early_warning"]
		self.assertTrue(all(row["follow_up_supported"] is False for row in r9))
		profit = next(row for row in r9 if row.get("family") == "Profitability")
		self.assertEqual(profit["open_mode"], "new_tab")

	def test_service_preserves_existing_action_center_and_does_not_mutate_business_documents(self):
		source = (APP_ROOT / "business_control_center.py").read_text()
		self.assertIn("get_action_center_data", source)
		self.assertIn("get_control_early_warning", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("save(", source)
		self.assertIn("do not create a ledger", source)
		self.assertIn("follow-up validator", source)


if __name__ == "__main__":
	unittest.main()
