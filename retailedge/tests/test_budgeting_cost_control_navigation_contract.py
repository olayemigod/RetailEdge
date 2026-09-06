from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from retailedge.edgesuite_ui import NAVIGATION_GROUPS


APP_ROOT = Path(__file__).resolve().parents[1]
APPROVED_NATIVE_TARGETS = [
	("DocType", "Budget"),
	("Report", "Budget Variance Report"),
	("DocType", "Cost Center"),
]


class TestBudgetingCostControlNavigationContract(TestCase):
	def test_accounting_group_exposes_native_budgeting_targets(self):
		groups = [group for group in NAVIGATION_GROUPS if group["key"] == "accounting"]
		self.assertEqual(len(groups), 1)

		group = groups[0]
		self.assertEqual(
			set(group["required_roles"]),
			{"Accounts User", "Accounts Manager", "System Manager"},
		)
		items = list(group["items"])
		actual_targets = [(item["target_type"], item["target"]) for item in items]
		for target in APPROVED_NATIVE_TARGETS:
			self.assertIn(target, actual_targets)
			self.assertEqual(actual_targets.count(target), 1)

		first_budget_index = actual_targets.index(APPROVED_NATIVE_TARGETS[0])
		self.assertEqual(
			actual_targets[first_budget_index : first_budget_index + len(APPROVED_NATIVE_TARGETS)],
			APPROVED_NATIVE_TARGETS,
		)

	def test_native_document_and_report_permission_gates_are_preserved(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		group_start = source.index('"key": "accounting"')
		group_end = source.index('"key": "setup"', group_start)
		group = source[group_start:group_end]

		self.assertIn('"target_type": "DocType", "target": "Budget"', group)
		self.assertIn('"target_type": "Report", "target": "Budget Variance Report"', group)
		self.assertIn('"target_type": "DocType", "target": "Cost Center"', group)
		self.assertIn('if target_type == "DocType":', source)
		self.assertIn('_has_permission_cached(target, "read", permission_cache)', source)
		self.assertIn('if target_type == "Report":', source)
		self.assertIn("get_report_doc(report_name)", source)

	def test_retailedge_does_not_create_a_parallel_budget_engine(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()

		for forbidden in (
			"RetailEdge Budget",
			"budget ledger",
			"create_budget",
			"submit_budget",
			"ignore_permissions",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	import unittest

	unittest.main()
