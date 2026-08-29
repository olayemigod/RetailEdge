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
