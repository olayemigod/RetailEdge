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

	def test_dashboard_explains_budget_limit_and_account_permission(self):
		backend = (APP_ROOT / "expense_dashboard.py").read_text(encoding="utf-8")
		vue = (APP_ROOT / "public/js/expense_dashboard/ExpenseDashboard.vue").read_text(encoding="utf-8")
		self.assertIn("Budget compliance is not inferred", backend)
		self.assertIn('frappe.has_permission("Account", "read")', backend)
		self.assertIn("Payment accounts used to fund expenses", vue)


if __name__ == "__main__":
	unittest.main()
