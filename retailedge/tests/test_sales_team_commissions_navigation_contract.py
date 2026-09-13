from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from retailedge.edgesuite_ui import NAVIGATION_GROUPS


APP_ROOT = Path(__file__).resolve().parents[1]
APPROVED_NATIVE_TARGETS = [
	("DocType", "Sales Person"),
	("DocType", "Sales Partner"),
	("Report", "Sales Person Commission Summary"),
	("Report", "Sales Partner Commission Summary"),
	("Report", "Sales Person Target Variance Based On Item Group"),
	("Report", "Sales Partner Target Variance based on Item Group"),
]


class TestSalesTeamCommissionNavigationContract(TestCase):
	def test_sell_group_exposes_native_sales_team_and_commission_targets(self):
		groups = [group for group in NAVIGATION_GROUPS if group["key"] == "sell"]
		self.assertEqual(len(groups), 1)

		items = list(groups[0]["items"])
		actual_targets = [(item["target_type"], item["target"]) for item in items]
		for target in APPROVED_NATIVE_TARGETS:
			self.assertIn(target, actual_targets)
			self.assertEqual(actual_targets.count(target), 1)

		first_sales_team_index = actual_targets.index(APPROVED_NATIVE_TARGETS[0])
		self.assertEqual(
			actual_targets[first_sales_team_index : first_sales_team_index + len(APPROVED_NATIVE_TARGETS)],
			APPROVED_NATIVE_TARGETS,
		)

	def test_native_permission_gates_remain_authoritative(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		group_start = source.index('"key": "sell"')
		group_end = source.index('"key": "pricing-promotions"', group_start)
		group = source[group_start:group_end]

		self.assertNotIn("required_roles", group)
		self.assertIn('if target_type == "DocType":', source)
		self.assertIn('_has_permission_cached(target, "read", permission_cache)', source)
		self.assertIn('if target_type == "Report":', source)
		self.assertIn("get_report_doc(report_name)", source)

	def test_retailedge_does_not_create_a_parallel_commission_or_payout_engine(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()

		self.assertNotIn('"target_type": "DocType", "target": "Sales Commission"', source)
		for forbidden in (
			"Additional Salary",
			"Salary Slip",
			"commission payout",
			"create_commission",
			"pay_commission",
			"ignore_permissions",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	import unittest

	unittest.main()
