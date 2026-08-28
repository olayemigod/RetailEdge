from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.master_experience import SETUP_MANAGED_DOCTYPES

APP_ROOT = Path(__file__).resolve().parents[1]


class TestR7SetupConsolidation(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_branch_setup_rejects_cross_company_and_non_leaf_defaults(self):
		source = self.read("branch_profile.py")
		for contract in (
			"COMPANY_LINK_FIELDS",
			"LEAF_FIELDS",
			'_validate_company_links(doc)',
			'_validate_leaf_defaults(doc)',
			'"default_pos_profile": ("POS Profile", "company")',
			'"default_warehouse": ("Warehouse", "company")',
			'"default_cost_center": ("Cost Center", "company")',
			'"default_cash_account": ("Account", "company")',
			'"company": doc.company',
			'"branch": doc.branch',
			"must belong to Company",
			"must be a leaf",
			"must be enabled",
		):
			self.assertIn(contract, source)
		self.assertNotIn('"branch": ("Branch", "company")', source)
		self.assertNotIn('frappe.db.exists("Branch", doc.branch)', source)
		self.assertNotIn("_validate_branch_reference", source)

	def test_branch_setup_form_filters_company_bound_defaults(self):
		source = self.read("retailedge/doctype/retailedge_branch_profile/retailedge_branch_profile.js")
		for contract in (
			"COMPANY_DEPENDENT_FIELDS",
			"setCompanyDependentQueries(frm)",
			'frm.set_query("default_pos_profile"',
			"WAREHOUSE_FIELDS.forEach",
			"COST_CENTER_FIELDS.forEach",
			"ACCOUNT_FIELDS.forEach",
			"{ is_group: 0, disabled: 0 }",
			"clearIdentityDependentDefaults(frm)",
			"company(frm)",
		):
			self.assertIn(contract, source)
		# ERPNext v16 Branch has no native Company field. RetailEdge may therefore
		# query Branch only through its own Branch Setup mapping authority; it must
		# never pretend the ERPNext Branch master itself has a Company field.
		self.assertIn('frm.set_query("branch"', source)
		self.assertIn(
			"retailedge.branch_profile_queries.search_available_branch_setup_branches",
			source,
		)
		self.assertNotIn('frm.set_query("branch", () => companyFilters', source)

	def test_branch_setup_validation_does_not_add_accounting_or_stock_writes(self):
		source = self.read("branch_profile.py")
		for forbidden in (
			"ignore_permissions=True",
			"frappe.db.commit",
			'frappe.new_doc("GL Entry")',
			'frappe.new_doc("Stock Ledger Entry")',
		):
			self.assertNotIn(forbidden, source)

	def test_setup_route_consolidation_is_server_shared_and_permission_gated(self):
		source = self.read("master_experience.py")
		for contract in (
			"SETUP_HUB_ITEM",
			"SETUP_MANAGED_DOCTYPES",
			"_consolidate_setup_navigation",
			'_can_open_page(SETUP_HUB_ITEM["target"])',
			'"target": "retailedge-setup"',
			'feature_flags["setup_route_consolidation"] = "edgesuite_setup"',
		):
			self.assertIn(contract, source)

	def test_setup_consolidation_keeps_native_erpnext_fallbacks(self):
		source = self.read("master_experience.py")
		for managed_doctype in (
			"RetailEdge Settings",
			"RetailEdge Branch Profile",
			"RetailEdge Expense Category",
			"RetailEdge Statement Mapping Template",
		):
			self.assertIn(managed_doctype, source)
		self.assertNotIn("Bank Account", SETUP_MANAGED_DOCTYPES)
		self.assertNotIn("Mode of Payment", SETUP_MANAGED_DOCTYPES)
		self.assertNotIn("frappe.set_route =", source)
		self.assertNotIn("window.history", source)

	def test_setup_context_is_permission_filtered_and_bounded(self):
		source = self.read("retailedge/page/retailedge_setup/retailedge_setup.py")
		for contract in (
			"frappe.has_permission",
			"frappe.get_list",
			"limit_page_length=limit",
			'"can_create"',
			'"count_capped"',
		):
			self.assertIn(contract, source)
		self.assertNotIn("frappe.get_all", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)


if __name__ == "__main__":
	unittest.main()
