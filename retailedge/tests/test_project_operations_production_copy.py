from __future__ import annotations

from pathlib import Path
from unittest import TestCase

APP_ROOT = Path(__file__).resolve().parents[1]
COMPONENT = APP_ROOT / "public" / "js" / "project_operations" / "ProjectOperations.vue"
ACTIVITY = APP_ROOT / "project_activity.py"
BUDGET = APP_ROOT / "project_budget.py"


class TestProjectOperationsProductionCopy(TestCase):
	def test_project_operations_uses_business_copy_and_preserves_workflow_contracts(self):
		component = COMPONENT.read_text(encoding="utf-8")
		activity = ACTIVITY.read_text(encoding="utf-8")
		budget = BUDGET.read_text(encoding="utf-8")

		for marker in (
			"Operational and financial visibility across Projects, Tasks, Budgets, Payment Entries and project accounting dimensions.",
			"Project identity, costing, billing and margin follow the project accounting records.",
			"Project Tasks drive this operational view.",
			"Project Budget controls govern this spending view.",
			"Read-only view of permitted Sales Orders, Sales Invoices, Purchase Invoices, Expense Claims and Stock Entries linked to this Project.",
			"Submitted incoming Payment Entries explicitly linked to this Project.",
			"Submitted outgoing Payment Entries explicitly linked to this Project.",
			"There is no project wallet, task ledger, budget ledger or separate accounting ledger.",
			"Create navigation is unavailable. Refresh the page or contact your administrator.",
		):
			self.assertIn(marker, component)

		for forbidden in (
			"Open ERPNext Project",
			"Advanced workflow: Native Desk access is required",
			"ERPNext Project remains authoritative",
			"ERPNext Task remains the operational source of truth",
			"ERPNext Budget remains the governance authority",
			"ERPNext Project Budgets",
			"ERPNext Payment Entries",
			"EdgeSuite create navigation is unavailable",
		):
			self.assertNotIn(forbidden, component)

		self.assertIn("Project Tasks and Milestones are whole-project operational records; Branch filtering does not narrow them.", activity)
		self.assertIn("Project Budgets are whole-project controls. Branch filtering does not alter Budget scope.", budget)
		self.assertIn("Budget enforcement uses the configured Stop/Warn/Ignore controls; this workflow does not bypass them.", budget)

		for marker in (
			"canUseNativeDesk",
			"window.EdgeSuiteUI?.openCreateSurface",
			"retailedge.project_search.search_projects",
			"retailedge.project_operations.get_project_funds_context",
			"retailedge.project_activity.get_project_activity_context",
			"retailedge.project_budget.get_project_budget_context",
			"retailedge.project_receipts.create_project_receipt_draft",
			"retailedge.project_expense_routing.get_project_expense_routes",
			'frappe.set_route("query-report", "RetailEdge Project Financial Control"',
		):
			self.assertIn(marker, component)


if __name__ == "__main__":
	import unittest

	unittest.main()
