from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestProjectFinancialControlReportContract(TestCase):
	def test_report_is_standard_whole_project_financial_control(self):
		report_dir = APP_ROOT / "retailedge" / "report" / "retailedge_project_financial_control"
		report_json = (report_dir / "retailedge_project_financial_control.json").read_text()
		report_js = (report_dir / "retailedge_project_financial_control.js").read_text()
		report_py = (report_dir / "retailedge_project_financial_control.py").read_text()

		self.assertIn('"name": "RetailEdge Project Financial Control"', report_json)
		self.assertIn('"ref_doctype": "Project"', report_json)
		self.assertIn('fieldname: "company"', report_js)
		self.assertIn('fieldname: "project"', report_js)
		self.assertIn('filters: { company: frappe.query_report.get_filter_value("company") }', report_js)
		self.assertNotIn('fieldname: "branch"', report_js)
		self.assertIn("Whole-project report", report_py)

	def test_report_uses_native_erpnext_financial_sources(self):
		report_py = (APP_ROOT / "retailedge" / "report" / "retailedge_project_financial_control" / "retailedge_project_financial_control.py").read_text()

		for source in ("Project", "Payment Entry", "Sales Invoice", "Purchase Invoice", "Budget"):
			self.assertIn(f'"{source}"', report_py)
		self.assertIn('"docstatus": 1', report_py)
		self.assertIn('"outstanding_amount": ["!=", 0]', report_py)
		self.assertIn('"budget_against": "Project"', report_py)
		self.assertIn('group_by="project"', report_py)
		self.assertIn("MAX_PROJECT_ROWS = 500", report_py)

	def test_report_distinguishes_cash_ar_ap_budget_cost_and_margin(self):
		report_py = (APP_ROOT / "retailedge" / "report" / "retailedge_project_financial_control" / "retailedge_project_financial_control.py").read_text()

		for fieldname in (
			"receivable_outstanding",
			"payable_outstanding",
			"project_cash_in",
			"project_cash_out",
			"net_project_cash",
			"submitted_budget",
			"budget_remaining",
			"purchase_cost",
			"consumed_material_cost",
			"timesheet_cost",
			"tracked_cost",
			"gross_margin",
		):
			self.assertIn(f'"{fieldname}"', report_py)
		self.assertIn("not revenue, expense, profit or bank balance", report_py)
		self.assertIn("Budget values are hidden", report_py)

	def test_report_enforces_source_read_permissions(self):
		report_py = (APP_ROOT / "retailedge" / "report" / "retailedge_project_financial_control" / "retailedge_project_financial_control.py").read_text()

		self.assertIn('_require_read("Project")', report_py)
		self.assertIn('_require_read("Payment Entry")', report_py)
		self.assertIn('_require_read("Sales Invoice")', report_py)
		self.assertIn('_require_read("Purchase Invoice")', report_py)
		self.assertIn('frappe.has_permission("Budget", "read")', report_py)
		self.assertNotIn("ignore_permissions=True", report_py)


if __name__ == "__main__":
	import unittest
	unittest.main()
