from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.operating_context import _allowed_branches, validate_operating_branch


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


class WorkingBranchOptionTests(unittest.TestCase):
	def test_active_assignment_is_not_hidden_by_missing_branch_setup_profile(self):
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
				return_value=[{"branch": "Ketu"}],
			),
			patch(
				"retailedge.operating_context.get_assignment_branches",
				return_value=["Ketu", "Lagos Island"],
			),
		):
			self.assertEqual(
				_allowed_branches(company="RetailEdge Consulting", user="branch-user@example.com"),
				["Ketu", "Lagos Island"],
			)

	def test_permitted_assigned_branch_can_be_selected_without_branch_defaults_profile(self):
		with (
			patch("retailedge.operating_context._assert_company_access"),
			patch("retailedge.operating_context._assert_branch_exists_and_active"),
			patch("retailedge.operating_context._branch_company", return_value=""),
			patch("retailedge.operating_context.get_enabled_branch_profile_companies", return_value=[]),
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


class WorkingBranchListScopeContractTests(unittest.TestCase):
	def test_shared_document_scope_uses_stored_branch_attribution(self):
		source = (APP_ROOT / "public/js/working_branch_document_scope.js").read_text(encoding="utf-8")
		for contract in (
			"retailedge_branch",
			"active_branch",
			"filter_area",
			"before_refresh",
			"filter_area.clear(false)",
			"filter_area.set(nextFilters)",
			"Sales Invoice",
			"Purchase Invoice",
			"Stock Entry",
			"Payment Entry",
		):
			self.assertIn(contract, source)

	def test_existing_list_filters_are_preserved_and_working_branch_replaces_stale_branch(self):
		source = (APP_ROOT / "public/js/working_branch_document_scope.js").read_text(encoding="utf-8")
		preserve = source.index("const preservedFilters = currentFilters.filter")
		branch_filter = source.index("[listview.doctype, fieldname, \"=\", branch]")
		self.assertLess(preserve, branch_filter)
		self.assertIn("!isBranchFilter(filter, listview.doctype, fieldname)", source)

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

	def test_browser_gate_runs_working_branch_scope_acceptance(self):
		workflow = (REPO_ROOT / ".github/workflows/browser-persona-smoke.yml").read_text(encoding="utf-8")
		self.assertIn("browser-tests/retailedge_working_branch_scope.spec.cjs", workflow)


if __name__ == "__main__":
	unittest.main()
