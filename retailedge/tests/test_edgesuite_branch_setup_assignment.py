from __future__ import annotations

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
BRANCH_SETUP_VUE = APP_ROOT / "public" / "js" / "branch_setup" / "BranchSetup.vue"
BRANCH_ASSIGNMENTS_VUE = APP_ROOT / "public" / "js" / "branch_assignments" / "BranchAssignments.vue"
BRANCH_SETUP_SERVICE = APP_ROOT / "branch_setup.py"
BRANCH_ASSIGNMENT_UI = APP_ROOT / "branch_assignment_ui.py"
BRANCH_SETUP_PAGE = APP_ROOT / "retailedge" / "page" / "branch_setup" / "branch_setup.json"
SETUP_HUB = APP_ROOT / "retailedge" / "page" / "retailedge_setup" / "retailedge_setup.py"


class TestEdgeSuiteBranchSetupAssignment(unittest.TestCase):
	def test_branch_setup_is_first_class_edgesuite_page(self):
		source = BRANCH_SETUP_VUE.read_text(encoding="utf-8")
		for contract in (
			"EdgeAppShell",
			"EdgePageLayout",
			"EdgePageHeader",
			"EdgeModal",
			"EdgeLinkField",
			"/app/branch-setup",
			"Add Branch Setup",
			"Branch Assignments",
			"Change Company / Branch",
			"Open Full Form",
			"retailedge.branch_setup.search_branch_setup_options",
			"reassign_branch_profile",
		):
			self.assertIn(contract, source)
		self.assertNotIn("new frappe.ui.Dialog", source)

	def test_branch_assignments_uses_edgesuite_modals_and_links(self):
		source = BRANCH_ASSIGNMENTS_VUE.read_text(encoding="utf-8")
		for contract in (
			"EdgeAppShell",
			"EdgeModal",
			"EdgeLinkField",
			"Assign User to Branch",
			"Transfer User to Branch",
			"retailedge.branch_assignment_ui.search_branch_assignment_options",
			"previous assignment preserved",
			"Branch Setup",
		):
			self.assertIn(contract, source)
		self.assertNotIn("new frappe.ui.Dialog", source)

	def test_branch_setup_page_registration_and_setup_hub_route(self):
		definition = json.loads(BRANCH_SETUP_PAGE.read_text(encoding="utf-8"))
		self.assertEqual(definition["page_name"], "branch-setup")
		self.assertEqual(definition["title"], "Branch Setup")
		setup = SETUP_HUB.read_text(encoding="utf-8")
		self.assertIn('"page": "branch-setup"', setup)
		self.assertIn('"page": "branch-assignments"', setup)
		self.assertIn('and not definition.get("page")', setup)

	def test_branch_setup_backend_is_permission_aware_and_reuses_doctype_validation(self):
		source = BRANCH_SETUP_SERVICE.read_text(encoding="utf-8")
		for contract in (
			"frappe.has_permission(BRANCH_SETUP_DOCTYPE, \"read\")",
			"doc.check_permission(\"write\")",
			"doc.insert()",
			"doc.save()",
			"get_branch_profile_reassignment_state",
			"search_available_branch_setup_branches",
			"search_reassignment_target_branches",
			"search_configured_company_branches",
		):
			self.assertIn(contract, source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit", source)

	def test_assignment_search_is_smart_and_does_not_widen_access(self):
		source = BRANCH_ASSIGNMENT_UI.read_text(encoding="utf-8")
		for contract in (
			'filters={"enabled": 1, "user_type": "System User"}',
			"search_configured_company_branches",
			"if not company:",
			"frappe.has_permission(ASSIGNMENT_DOCTYPE, \"read\")",
		):
			self.assertIn(contract, source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.get_all", source)


if __name__ == "__main__":
	unittest.main()
