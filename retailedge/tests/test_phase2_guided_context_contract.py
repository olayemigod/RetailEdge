from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.guided_entry_context import (
	get_guided_branch_names,
	get_guided_warehouse_search_filters,
	resolve_guided_branch,
	validate_guided_branch_warehouse,
)


ROOT = Path(__file__).resolve().parents[1]
SALES = ROOT / "guided_sales_invoice.py"
STOCK = ROOT / "guided_stock_transfer.py"
PURCHASE = ROOT / "guided_purchase_invoice.py"
CONTEXT = ROOT / "guided_entry_context.py"
SALES_UI = ROOT / "public/js/retailedge_business_hub/SimpleSalesInvoiceDialog.vue"
STOCK_UI = ROOT / "public/js/retailedge_business_hub/SimpleStockTransferDialog.vue"
PURCHASE_UI = ROOT / "public/js/retailedge_business_hub/SimplePurchaseInvoiceDialog.vue"
HUB = ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue"
COMPLETION = ROOT / "standard_sales_invoice_completion.py"
SETTINGS = ROOT / "retailedge/doctype/retailedge_settings/retailedge_settings.json"


class TestPhase2GuidedContextContract(unittest.TestCase):
	@patch(
		"retailedge.guided_entry_context.get_operational_branch_scope",
		return_value={"restricted": True, "allowed_branches": ["Lagos", "Abuja"]},
	)
	@patch(
		"retailedge.guided_entry_context.get_enabled_branch_profiles",
		return_value=[
			frappe._dict(branch="Lagos"),
			frappe._dict(branch="Ketu 2"),
		],
	)
	def test_configured_branches_are_intersected_with_operational_scope(
		self, _mock_profiles, _mock_scope
	):
		self.assertEqual(
			get_guided_branch_names("RetailEdge Consulting", user="user@example.com"),
			["Lagos"],
		)

	@patch(
		"retailedge.guided_entry_context.get_operational_branch_scope",
		return_value={"restricted": False, "allowed_branches": []},
	)
	@patch(
		"retailedge.guided_entry_context.get_enabled_branch_profiles",
		return_value=[frappe._dict(branch="Lagos")],
	)
	def test_unconfigured_explicit_branch_is_rejected(
		self, _mock_profiles, _mock_scope
	):
		with self.assertRaises(frappe.ValidationError):
			resolve_guided_branch(
				"RetailEdge Consulting",
				"Ketu 2",
				user="user@example.com",
			)

	@patch(
		"retailedge.guided_entry_context.get_guided_branch_names",
		return_value=["Lagos", "Abuja"],
	)
	@patch("retailedge.guided_entry_context.has_field", return_value=True)
	def test_warehouse_search_stays_closed_until_branch_is_selected(
		self, _mock_has_field, _mock_branches
	):
		self.assertIsNone(
			get_guided_warehouse_search_filters(
				"RetailEdge Consulting", "", user="user@example.com"
			)
		)

	@patch("retailedge.guided_entry_context._assert_read_permission")
	@patch(
		"retailedge.guided_entry_context.resolve_branch_from_warehouse",
		return_value={"branch": "Abuja"},
	)
	@patch(
		"retailedge.guided_entry_context.frappe.db.get_value",
		return_value="RetailEdge Consulting",
	)
	@patch(
		"retailedge.guided_entry_context.resolve_guided_branch",
		return_value="Lagos",
	)
	def test_server_revalidates_branch_warehouse_combination(
		self,
		_mock_branch,
		_mock_company,
		_mock_warehouse_branch,
		_mock_permission,
	):
		with self.assertRaises(frappe.ValidationError):
			validate_guided_branch_warehouse(
				company="RetailEdge Consulting",
				branch="Lagos",
				warehouse="Abuja Stores - RC",
				user="user@example.com",
			)

	def test_all_guided_transaction_adapters_use_shared_branch_setup_contract(self):
		for path in (SALES, STOCK, PURCHASE):
			source = path.read_text(encoding="utf-8")
			self.assertIn("get_guided_branch_names", source, path)
			self.assertIn("resolve_guided_branch", source, path)
			self.assertIn("get_guided_branch_search_filters", source, path)
			self.assertIn("get_guided_warehouse_search_filters", source, path)
			self.assertIn("validate_guided_branch_warehouse", source, path)
			self.assertIn("get_operating_context", source, path)

	def test_frontend_cascade_is_branch_first_when_branch_setup_exists(self):
		sales = SALES_UI.read_text(encoding="utf-8")
		stock = STOCK_UI.read_text(encoding="utf-8")
		purchase = PURCHASE_UI.read_text(encoding="utf-8")

		self.assertIn('requiresBranchSelection && !values.branch', sales)
		self.assertIn("transactionContextReady", sales)
		self.assertIn("canEditUpdateStock", sales)

		self.assertIn('requiresBranchSelection && !values.source_branch', stock)
		self.assertIn('requiresBranchSelection && !values.target_branch', stock)
		self.assertIn("transferContextReady", stock)

		self.assertIn('requiresBranchSelection && !values.branch', purchase)
		self.assertIn("transactionContextReady", purchase)
		self.assertIn("Buying Price List", purchase)

	def test_make_a_sale_update_stock_policy_is_settings_controlled_and_server_enforced(self):
		settings = SETTINGS.read_text(encoding="utf-8")
		sales = SALES.read_text(encoding="utf-8")
		sales_ui = SALES_UI.read_text(encoding="utf-8")

		self.assertIn('"allow_guided_sales_update_stock_edit"', settings)
		self.assertIn('"update_stock": 1', sales)
		self.assertIn("can_edit_update_stock", sales)
		self.assertIn("if can_edit_update_stock else 1", sales)
		self.assertIn(':disabled="!canEditUpdateStock"', sales_ui)

	def test_purchase_rates_remain_server_resolved_from_buying_context(self):
		source = PURCHASE.read_text(encoding="utf-8")
		self.assertIn('mode="buying"', source)
		self.assertIn("resolve_purchase_item_pricing(", source)
		self.assertIn("doc.buying_price_list", source)
		self.assertNotIn('values.get("buying_price_list")', source)

	def test_cashier_expense_save_stays_in_edgesuite(self):
		source = HUB.read_text(encoding="utf-8")
		self.assertIn("{ stayInEdgeSuite: true }", source)
		start = source.index("handleSimpleCashierExpenseSaved(result)")
		end = source.index("openNativeCashierExpense", start)
		handler = source[start:end]
		self.assertNotIn("frappe.set_route", handler)
		self.assertNotIn("frappe.new_doc", handler)
		self.assertIn("refreshHomeSnapshot()", handler)

	def test_sales_completion_uses_branch_setup_aware_warehouse_resolution(self):
		source = COMPLETION.read_text(encoding="utf-8")
		self.assertIn("resolve_branch_warehouse_selection(", source)
		self.assertIn('preference="sales"', source)
		self.assertNotIn("resolve_branch_from_warehouse", source)
		self.assertIn("not configured in an enabled Branch Setup", source)

	def test_shared_context_never_broadens_permissions(self):
		source = CONTEXT.read_text(encoding="utf-8")
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit", source)


if __name__ == "__main__":
	unittest.main()
