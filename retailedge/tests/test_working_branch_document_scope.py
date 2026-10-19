from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.operating_context import (
	_allowed_branches,
	can_use_company_wide_branch_view,
	validate_operating_branch,
)


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


class WorkingBranchOptionTests(unittest.TestCase):
	def test_active_assignments_are_exposed_when_branch_setup_binds_both_branches(self):
		with (
			patch("retailedge.operating_context._doctype_has_field", return_value=False),
			patch("retailedge.operating_context.user_has_global_branch_access", return_value=False),
			patch("retailedge.operating_context.has_branch_assignments", return_value=True),
			patch(
				"retailedge.operating_context.frappe.get_all",
				return_value=[{"name": "Ketu"}, {"name": "Lagos Island"}],
			),
			patch(
				"retailedge.operating_context.get_enabled_branch_profiles",
				return_value=[
					{"branch": "Ketu", "company": "RetailEdge Consulting"},
					{"branch": "Lagos Island", "company": "RetailEdge Consulting"},
				],
			),
			patch("retailedge.operating_context.frappe.db.exists", return_value=True),
			patch(
				"retailedge.operating_context.get_assignment_branches",
				return_value=["Ketu", "Lagos Island"],
			),
		):
			self.assertEqual(
				_allowed_branches(company="RetailEdge Consulting", user="branch-user@example.com"),
				["Ketu", "Lagos Island"],
			)

	def test_assignment_does_not_bypass_branch_setup_company_binding(self):
		with (
			patch("retailedge.operating_context._doctype_has_field", return_value=False),
			patch("retailedge.operating_context.user_has_global_branch_access", return_value=False),
			patch("retailedge.operating_context.has_branch_assignments", return_value=True),
			patch(
				"retailedge.operating_context.frappe.get_all",
				return_value=[{"name": "Ketu"}, {"name": "Lagos Island"}],
			),
			patch(
				"retailedge.operating_context.get_enabled_branch_profiles",
				return_value=[{"branch": "Ketu", "company": "RetailEdge Consulting"}],
			),
			patch("retailedge.operating_context.frappe.db.exists", return_value=True),
			patch(
				"retailedge.operating_context.get_assignment_branches",
				return_value=["Ketu", "Lagos Island"],
			),
		):
			self.assertEqual(
				_allowed_branches(company="RetailEdge Consulting", user="branch-user@example.com"),
				["Ketu"],
			)

	def test_permitted_assigned_branch_can_be_selected_when_branch_setup_has_no_defaults(self):
		with (
			patch("retailedge.operating_context._assert_company_access"),
			patch("retailedge.operating_context._assert_branch_exists_and_active"),
			patch("retailedge.operating_context._branch_company", return_value=""),
			patch(
				"retailedge.operating_context.get_enabled_branch_profiles",
				return_value=[{"branch": "Lagos Island", "company": "RetailEdge Consulting"}],
			),
			patch("retailedge.operating_context.frappe.db.exists", return_value=True),
			patch(
				"retailedge.operating_context.get_enabled_branch_profile_companies",
				return_value=["RetailEdge Consulting"],
			),
			patch("retailedge.operating_context.user_has_global_branch_access", return_value=False),
			patch("retailedge.operating_context.has_branch_assignments", return_value=True),
			patch(
				"retailedge.operating_context.get_assignment_branches",
				return_value=["Ketu", "Lagos Island"],
			),
			patch(
				"retailedge.operating_context._allowed_branches",
				return_value=["Ketu", "Lagos Island"],
			),
		):
			self.assertEqual(
				validate_operating_branch(
					company="RetailEdge Consulting",
					branch="Lagos Island",
					user="branch-user@example.com",
				),
				{
					"allowed": True,
					"company": "RetailEdge Consulting",
					"branch": "Lagos Island",
					"reason": "validated",
				},
			)

	def test_unrestricted_user_can_use_company_wide_branch_view(self):
		with (
			patch("retailedge.operating_context._assert_company_access"),
			patch(
				"retailedge.operating_context.get_operational_branch_scope",
				return_value={"restricted": False, "source": "global", "allowed_branches": []},
			),
			patch("retailedge.operating_context._allowed_branches", return_value=["Ketu", "Lagos Island"]),
		):
			self.assertTrue(
				can_use_company_wide_branch_view(
					company="RetailEdge Consulting",
					user="Administrator",
				)
			)

	def test_restricted_user_cannot_use_company_wide_branch_view(self):
		with (
			patch("retailedge.operating_context._assert_company_access"),
			patch(
				"retailedge.operating_context.get_operational_branch_scope",
				return_value={
					"restricted": True,
					"source": "branch_assignment",
					"allowed_branches": ["Ketu", "Lagos Island"],
				},
			),
			patch("retailedge.operating_context._allowed_branches", return_value=["Ketu", "Lagos Island"]),
		):
			self.assertFalse(
				can_use_company_wide_branch_view(
					company="RetailEdge Consulting",
					user="branch-user@example.com",
				)
			)


class WorkingBranchListScopeContractTests(unittest.TestCase):
	def test_shared_document_scope_uses_stored_branch_attribution(self):
		source = (APP_ROOT / "public/js/working_branch_document_scope.js").read_text(encoding="utf-8")
		for contract in (
			"retailedge_branch",
			"active_branch",
			"active_company",
			"company_wide",
			"filter_area",
			"listview.refresh",
			"filter_area.clear(false)",
			"filter_area.set(nextFilters)",
			"Sales Invoice",
			"Purchase Invoice",
			"Stock Entry",
			"Payment Entry",
		):
			self.assertIn(contract, source)

	def test_existing_filters_are_preserved_while_company_and_branch_scope_are_replaced(self):
		source = (APP_ROOT / "public/js/working_branch_document_scope.js").read_text(encoding="utf-8")
		preserve = source.index("const preservedFilters = currentFilters.filter")
		company_filter = source.index('[listview.doctype, companyFieldname, "=", company]')
		branch_filter = source.index('[listview.doctype, branchFieldname, "=", branch]')
		self.assertLess(preserve, company_filter)
		self.assertLess(company_filter, branch_filter)
		self.assertIn("!isFieldFilter(filter, listview.doctype, branchFieldname)", source)
		self.assertIn("!isFieldFilter(filter, listview.doctype, companyFieldname)", source)

	def test_company_wide_view_removes_branch_scope_only_with_company_boundary(self):
		source = (APP_ROOT / "public/js/working_branch_document_scope.js").read_text(encoding="utf-8")
		for contract in (
			"if (isCompanyWide && (!company || !companyFieldname))",
			"branchFilters.length === 0",
			"if (!isCompanyWide)",
			'nextFilters.push([listview.doctype, companyFieldname, "=", company])',
		):
			self.assertIn(contract, source)

	def test_live_listview_refresh_is_wrapped_after_erpnext_list_scripts_load(self):
		source = (APP_ROOT / "public/js/working_branch_document_scope.js").read_text(encoding="utf-8")
		for contract in (
			"const nativeRefresh = listview.refresh.bind(listview)",
			"listview.refresh = function (...args)",
			"Promise.resolve(apply(listview)).then(() => nativeRefresh(...args))",
			"function scheduleCurrentListviewInstall()",
			"for (const delay of [0, 50, 250, 750])",
			'frappe.router.on("change", scheduleCurrentListviewInstall)',
		):
			self.assertIn(contract, source)

	def test_specialized_purchase_and_cashier_lists_compose_working_branch_scope(self):
		purchase = (APP_ROOT / "public/js/purchase_documents_list.js").read_text(encoding="utf-8")
		cashier = (APP_ROOT / "public/js/retailedge_cashier_expense_list.js").read_text(encoding="utf-8")
		for source in (purchase, cashier):
			self.assertIn("workingBranchDocumentScope", source)
			self.assertIn("install?.(listview)", source)

	def test_helper_is_loaded_globally_and_purchase_order_uses_existing_list_module(self):
		hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
		self.assertIn('"/assets/retailedge/js/working_branch_document_scope.js"', hooks)
		self.assertIn('"Purchase Order": "public/js/purchase_documents_list.js"', hooks)
		self.assertNotIn('"Purchase Order": "public/js/purchase_order_list.js"', hooks)

	def test_selector_exposes_company_wide_only_through_server_authority(self):
		shell = (APP_ROOT / "public/js/retailedge_shell_context.js").read_text(encoding="utf-8")
		profile = (APP_ROOT / "company_profile.py").read_text(encoding="utf-8")
		page = (APP_ROOT / "public/js/operating_context/OperatingContext.vue").read_text(encoding="utf-8")
		for contract in (
			"COMPANY_WIDE_LABEL = \"All Branches\"",
			"can_view_all_branches",
			"switch_company_wide_context",
		):
			self.assertIn(contract, shell)
		self.assertIn("can_use_company_wide_branch_view", profile)
		self.assertIn("Use All Branches", page)
		self.assertIn("switch_company_wide_context", page)

	def test_browser_gate_runs_working_branch_scope_acceptance(self):
		workflow = (REPO_ROOT / ".github/workflows/browser-persona-smoke.yml").read_text(encoding="utf-8")
		self.assertIn("browser-tests/retailedge_working_branch_scope.spec.cjs", workflow)


if __name__ == "__main__":
	unittest.main()
