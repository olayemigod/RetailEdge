from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestProjectFinancialControlNavigationContract(TestCase):
	def test_financial_control_report_is_permission_governed_in_projects_navigation(self):
		source = (APP_ROOT / "master_experience.py").read_text()

		self.assertIn("PROJECT_FINANCIAL_CONTROL_REPORT_ITEM", source)
		self.assertIn('"target": "RetailEdge Project Financial Control"', source)
		self.assertIn('financial_control_available = _can_open_report(PROJECT_FINANCIAL_CONTROL_REPORT_ITEM["target"])', source)
		self.assertIn("deepcopy(PROJECT_FINANCIAL_CONTROL_REPORT_ITEM)", source)
		self.assertIn('feature_flags["project_financial_control"] = "whole_project_erpnext_financial_control"', source)

	def test_projects_navigation_still_preserves_native_project_fallback(self):
		source = (APP_ROOT / "master_experience.py").read_text()

		self.assertIn("PROJECT_OPERATIONS_ITEM", source)
		self.assertIn("PROJECT_PORTFOLIO_REPORT_ITEM", source)
		self.assertIn("PROJECT_LIST_ITEM", source)
		self.assertIn('frappe.has_permission("Project", "read")', source)


if __name__ == "__main__":
	import unittest
	unittest.main()
