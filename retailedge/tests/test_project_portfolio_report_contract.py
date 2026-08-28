from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestProjectPortfolioReportContract(TestCase):
	def test_report_is_standard_and_project_backed(self):
		report_dir = APP_ROOT / "retailedge" / "report" / "retailedge_project_portfolio"
		report_json = (report_dir / "retailedge_project_portfolio.json").read_text()
		report_py = (report_dir / "retailedge_project_portfolio.py").read_text()
		report_js = (report_dir / "retailedge_project_portfolio.js").read_text()

		self.assertIn('"name": "RetailEdge Project Portfolio"', report_json)
		self.assertIn('"ref_doctype": "Project"', report_json)
		self.assertIn('"report_type": "Script Report"', report_json)
		self.assertIn('fieldname: "company"', report_js)
		self.assertIn('fieldname: "customer"', report_js)
		self.assertIn('fieldname: "status"', report_js)
		self.assertIn('frappe.get_list(\n\t\t"Project"', report_py)
		self.assertIn('"Payment Entry"', report_py)
		self.assertIn('group_by="project"', report_py)
		self.assertIn('"docstatus": 1', report_py)
		self.assertIn("MAX_PROJECT_ROWS = 500", report_py)
		self.assertIn("not a bank balance or separate ledger", report_py)

	def test_report_is_governed_in_projects_navigation(self):
		source = (APP_ROOT / "master_experience.py").read_text()

		self.assertIn('"target": "RetailEdge Project Portfolio"', source)
		self.assertIn("PROJECT_PORTFOLIO_REPORT_ITEM", source)
		self.assertIn('feature_flags["project_portfolio_reporting"] = "erpnext_project_plus_payment_entries"', source)


if __name__ == "__main__":
	import unittest
	unittest.main()
