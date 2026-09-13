from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestExpenseDashboardShell(unittest.TestCase):
	def test_page_uses_edgesuite_dashboard_shell_and_shared_export(self):
		vue = (APP_ROOT / "public/js/expense_dashboard/ExpenseDashboard.vue").read_text(encoding="utf-8")
		bundle = (APP_ROOT / "public/js/expense_dashboard.bundle.js").read_text(encoding="utf-8")
		page = (APP_ROOT / "retailedge/page/expense_overview/expense_overview.js").read_text(encoding="utf-8")
		files = (APP_ROOT / "dashboard_files.py").read_text(encoding="utf-8")
		caps = (APP_ROOT / "dashboard_capabilities.py").read_text(encoding="utf-8")
		self.assertIn("EdgeDashboardShell", vue)
		self.assertIn("expense-overview", vue)
		self.assertIn("exportDashboard", vue)
		self.assertIn("printDashboard", vue)
		self.assertIn("createEdgeApp", bundle)
		self.assertIn("expense_dashboard.bundle.js", page)
		self.assertIn('"expense-overview"', files)
		self.assertIn('"expense-overview"', caps)

	def test_preview_is_not_promoted_to_normal_navigation_yet(self):
		for relative in (
			"retailedge/workspace/retailedge/retailedge.json",
			"retailedge/workspace_sidebar/retailedge/retailedge.json",
			"workspace_sidebar/retailedge.json",
		):
			text = (APP_ROOT / relative).read_text(encoding="utf-8")
			self.assertNotIn('"expense-overview"', text)

	def test_dashboard_explains_account_permissions_and_budget_source(self):
		backend = (APP_ROOT / "expense_dashboard.py").read_text(encoding="utf-8")
		budget = (APP_ROOT / "expense_budget.py").read_text(encoding="utf-8")
		budget_api = (APP_ROOT / "expense_budget_api.py").read_text(encoding="utf-8")
		vue = (APP_ROOT / "public/js/expense_dashboard/ExpenseDashboard.vue").read_text(encoding="utf-8")
		self.assertIn("Budget compliance is not inferred", backend)
		self.assertIn('frappe.has_permission("Account", "read")', backend)
		self.assertIn("Payment accounts used to fund expenses", vue)
		self.assertIn("Budget & Burn Rate", vue)
		self.assertIn("projected_over_budget", vue)
		self.assertIn("ambiguous_category_count", vue)
		self.assertIn("retailedge.expense_budget_api.get_expense_budget_insight", vue)
		self.assertIn('BUDGET_DOCTYPE = "Budget"', budget)
		self.assertIn('frappe.has_permission(BUDGET_DOCTYPE, "read")', budget)
		self.assertIn("get_expense_register_export", budget_api)

	def test_mtd_ytd_and_export_use_the_same_canonical_services(self):
		backend = (APP_ROOT / "expense_dashboard.py").read_text(encoding="utf-8")
		period = (APP_ROOT / "expense_period_context.py").read_text(encoding="utf-8")
		vue = (APP_ROOT / "public/js/expense_dashboard/ExpenseDashboard.vue").read_text(encoding="utf-8")
		self.assertIn("MTD & Calendar YTD", vue)
		self.assertIn("retailedge.expense_period_context.get_expense_period_context", vue)
		self.assertIn("get_expense_period_context(filters)", backend)
		self.assertIn("get_expense_budget_insight(filters)", backend)
		self.assertIn('_("Period Context")', backend)
		self.assertIn('_("Budget & Burn Rate")', backend)
		self.assertIn('"ytd_basis": "calendar_year"', period)
		self.assertIn("get_expense_register_export", period)


if __name__ == "__main__":
	unittest.main()
