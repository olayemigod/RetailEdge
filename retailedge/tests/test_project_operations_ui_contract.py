from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestProjectOperationsUIContract(TestCase):
	def test_project_operations_page_is_standard_edgesuite_page(self):
		page_dir = APP_ROOT / "retailedge" / "page" / "project_operations"
		page_json = (page_dir / "project_operations.json").read_text()
		page_js = (page_dir / "project_operations.js").read_text()
		self.assertIn('"page_name": "project-operations"', page_json)
		self.assertIn('"standard": "Yes"', page_json)
		self.assertIn('const EDGEUI_ASSET = "edgeui.bundle.js"', page_js)
		self.assertIn('const PROJECT_ASSET = "project_operations.bundle.js"', page_js)
		self.assertIn("window.mountProjectOperationsPage", page_js)

	def test_project_operations_uses_erpnext_native_sources(self):
		bundle = (APP_ROOT / "public" / "js" / "project_operations.bundle.js").read_text()
		component = (APP_ROOT / "public" / "js" / "project_operations" / "ProjectOperations.vue").read_text()
		self.assertIn("ProjectOperations", bundle)
		self.assertIn("retailedge.project_search.search_projects", component)
		self.assertIn("retailedge.project_operations.get_project_funds_context", component)
		self.assertIn("retailedge.project_activity.get_project_activity_context", component)
		self.assertIn("retailedge.project_budget.get_project_budget_context", component)
		self.assertIn("retailedge.project_receipts.create_project_receipt_draft", component)
		self.assertIn("retailedge.project_expense_routing.get_project_expense_routes", component)
		self.assertIn("Open ERPNext Project", component)
		self.assertIn("Record Project Cost", component)
		self.assertIn("frappe.new_doc(route.doctype, route.defaults || {})", component)
		self.assertIn("Payment Entry", component)
		self.assertIn("Project Transaction Timeline", component)
		self.assertIn("openTimelineDoc", component)
		self.assertIn("does not maintain a project wallet", component)
		self.assertNotIn("GL Entry", component)

	def test_project_branch_search_is_bounded_permission_aware_and_company_contextual(self):
		source = (APP_ROOT / "project_search.py").read_text()
		self.assertIn("def search_project_branches", source)
		self.assertIn('frappe.has_permission("Branch", "read")', source)
		self.assertIn("get_user_allowed_branches", source)
		self.assertIn("user_has_global_branch_access", source)
		self.assertIn('"RetailEdge Branch Profile"', source)
		self.assertIn('filters={"company": company, "enabled": 1}', source)
		self.assertIn("limit_page_length=page_length", source)
		self.assertNotIn('frappe.get_all(\n\t\t"Branch"', source)

	def test_project_operations_branch_field_uses_smart_cascading_selector(self):
		component = (APP_ROOT / "public" / "js" / "project_operations" / "ProjectOperations.vue").read_text()
		self.assertIn('label="Branch"', component)
		self.assertIn(':searcher="branchSearch"', component)
		self.assertIn('retailedge.project_search.search_project_branches', component)
		self.assertIn('company: this.projectCompany', component)
		self.assertIn('this.branch = ""; this.branchLabel = "";', component)
		self.assertIn('onBranchSelected(option)', component)
		self.assertIn('clearBranch()', component)
		self.assertNotIn('<input v-model="branch"', component)

	def test_project_receipt_inherits_validated_branch_scope(self):
		component = (APP_ROOT / "public" / "js" / "project_operations" / "ProjectOperations.vue").read_text()
		self.assertIn('{ fieldname: "branch", fieldtype: "Data", label: __("Branch"), default: this.branch || "", read_only: 1 }', component)

	def test_project_activity_uses_native_task_and_milestone_workflow(self):
		component = (APP_ROOT / "public" / "js" / "project_operations" / "ProjectOperations.vue").read_text()
		source = (APP_ROOT / "project_activity.py").read_text()
		self.assertIn("Tasks & Milestones", component)
		self.assertIn("Open Tasks", component)
		self.assertIn("New Task", component)
		self.assertIn('frappe.new_doc("Task", { project: this.project })', component)
		self.assertIn('frappe.set_route("List", "Task", { project: this.project })', component)
		self.assertIn('filters={"project": project, "is_template": 0}', source)
		self.assertIn('"is_milestone"', source)
		self.assertIn("MAX_PROJECT_TASK_ROWS = 500", source)
		self.assertIn('frappe.has_permission("Task", "read")', source)
		self.assertIn('frappe.has_permission("Task", "create")', source)
		self.assertNotIn("frappe.new_doc(", source)

	def test_project_budget_governance_uses_native_erpnext_budget(self):
		component = (APP_ROOT / "public" / "js" / "project_operations" / "ProjectOperations.vue").read_text()
		source = (APP_ROOT / "project_budget.py").read_text()
		self.assertIn("Project Budget Governance", component)
		self.assertIn("Open Budgets", component)
		self.assertIn("New Budget", component)
		self.assertIn('frappe.new_doc("Budget", { budget_against: "Project", project: this.project, company: this.context.company })', component)
		self.assertIn('budget_against: "Project"', component)
		self.assertIn('filters={"budget_against": "Project", "project": project, "company": doc.company, "docstatus": ["<", 2]}', source)
		self.assertIn('frappe.has_permission("Budget", "read")', source)
		self.assertIn('frappe.has_permission("Budget", "create")', source)
		self.assertIn("applicable_on_purchase_order", source)
		self.assertIn("applicable_on_booking_actual_expenses", source)
		self.assertIn("applicable_on_cumulative_expense", source)
		self.assertNotIn("ignore_permissions=True", source)

	def test_project_cash_and_cost_labels_are_not_accounting_claims(self):
		component = (APP_ROOT / "public" / "js" / "project_operations" / "ProjectOperations.vue").read_text()
		self.assertIn("Project Cash In", component)
		self.assertIn("Project Cash Out", component)
		self.assertIn("Net Project-linked Cash", component)
		self.assertIn("not revenue recognition", component)
		self.assertIn("not an expense/P&amp;L measure", component)
		self.assertIn("Purchase Cost", component)
		self.assertIn("Consumed Material Cost", component)
		self.assertIn("Timesheet Cost", component)

	def test_project_receipt_action_creates_draft_payment_entry(self):
		source = (APP_ROOT / "project_receipts.py").read_text()
		self.assertIn('doc = frappe.new_doc(PAYMENT_ENTRY_DOCTYPE)', source)
		self.assertIn('doc.payment_type = "Receive"', source)
		self.assertIn("doc.project = project", source)
		self.assertIn("doc.insert()", source)
		self.assertNotIn("doc.submit()", source)
		self.assertNotIn("ignore_permissions=True", source)

	def test_project_timeline_is_native_bounded_and_excludes_cancelled_documents(self):
		source = (APP_ROOT / "project_operations.py").read_text()
		self.assertIn("MAX_TIMELINE_ROWS = 200", source)
		self.assertIn('"Sales Order"', source)
		self.assertIn('"Sales Invoice"', source)
		self.assertIn('"Purchase Invoice"', source)
		self.assertIn('"Expense Claim"', source)
		self.assertIn('"Stock Entry"', source)
		self.assertIn('"docstatus": ["<", 2]', source)
		self.assertIn("if branch and not branch_field", source)
		self.assertIn("rows[:MAX_TIMELINE_ROWS]", source)

	def test_project_operations_is_governed_navigation_with_native_fallback(self):
		source = (APP_ROOT / "master_experience.py").read_text()
		self.assertIn('"target": "project-operations"', source)
		self.assertIn('"target": "Project"', source)
		self.assertIn("def _promote_project_operations", source)
		self.assertIn('"key": "projects"', source)
		self.assertIn("_promote_project_operations(navigation_groups)", source)
		self.assertIn('feature_flags["project_operations"] = "erpnext_native_project_funds"', source)

	def test_project_cost_router_does_not_create_generic_expense_entries(self):
		source = (APP_ROOT / "project_expense_routing.py").read_text()
		self.assertIn('doctype="Purchase Invoice"', source)
		self.assertIn('doctype="Stock Entry"', source)
		self.assertIn('doctype="Expense Claim"', source)
		self.assertIn('doctype="Journal Entry"', source)
		self.assertIn("which standard documents the current user can create", source)
		self.assertNotIn("frappe.new_doc(", source)
		self.assertNotIn("insert()", source)
		self.assertNotIn("submit()", source)


if __name__ == "__main__":
	import unittest
	unittest.main()
