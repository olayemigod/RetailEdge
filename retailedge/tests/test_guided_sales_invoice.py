from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.guided_sales_invoice import (
	MAX_ITEMS,
	MAX_LINK_RESULTS,
	_normalise_items,
	_validate_branch_warehouse,
	_warehouse_search_filters,
	create_simple_sales_invoice_draft,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _DraftSalesInvoice(SimpleNamespace):
	doctype = "Sales Invoice"

	def __init__(self):
		super().__init__(
			name="ACC-SINV-GUIDED-0001",
			docstatus=0,
			grand_total=3000.0,
			currency="NGN",
			items=[],
			insert_calls=0,
		)

	def append(self, table, row):
		self.items.append(frappe._dict(row))
		return self.items[-1]

	def insert(self):
		self.insert_calls += 1
		return self


class TestGuidedSalesInvoice(unittest.TestCase):
	def test_normalise_items_keeps_rate_optional_until_server_pricing(self):
		rows = _normalise_items(
			[
				{"item_code": "ITEM-001", "qty": 2, "rate": ""},
				{"item_code": "ITEM-002", "qty": "3", "rate": "1500"},
			]
		)
		self.assertEqual(rows[0], {"item_code": "ITEM-001", "qty": 2.0, "rate": None})
		self.assertEqual(rows[1], {"item_code": "ITEM-002", "qty": 3.0, "rate": 1500.0})

	def test_normalise_items_rejects_invalid_business_rows(self):
		for rows in (
			[],
			[{"item_code": "", "qty": 1}],
			[{"item_code": "ITEM-001", "qty": 0}],
			[{"item_code": "ITEM-001", "qty": 1, "rate": -1}],
			[{"item_code": "ITEM-001", "qty": 1}] * (MAX_ITEMS + 1),
		):
			with self.subTest(rows=len(rows)):
				with self.assertRaises(frappe.ValidationError):
					_normalise_items(rows)

	@patch(
		"retailedge.guided_sales_invoice.get_guided_warehouse_search_filters",
		return_value={"company": "Demo Company", "branch": "Lagos", "is_group": 0},
	)
	def test_warehouse_search_filters_company_and_branch_without_loading_all_rows(
		self,
		mock_filters,
	):
		filters = _warehouse_search_filters(
			company="Demo Company",
			branch="Lagos",
			user="sales@example.com",
		)
		self.assertEqual(filters["company"], "Demo Company")
		self.assertEqual(filters["branch"], "Lagos")
		self.assertEqual(filters["is_group"], 0)
		mock_filters.assert_called_once_with("Demo Company", "Lagos", user="sales@example.com")

	@patch(
		"retailedge.guided_sales_invoice.validate_guided_branch_warehouse",
		side_effect=frappe.ValidationError("Branch mismatch"),
	)
	def test_branch_warehouse_mismatch_is_blocked(self, mock_validate):
		with self.assertRaises(frappe.ValidationError):
			_validate_branch_warehouse(
				branch="Lagos",
				warehouse="Abuja Store",
				company="Demo Company",
				user="sales@example.com",
			)
		mock_validate.assert_called_once()

	@patch("retailedge.guided_sales_invoice.resolve_sales_item_pricing")
	@patch("retailedge.guided_sales_invoice.resolve_price_list_context")
	@patch("retailedge.guided_sales_invoice.get_retailedge_settings", return_value=SimpleNamespace(allow_guided_sales_update_stock_edit=1))
	@patch("retailedge.guided_sales_invoice.get_guided_branch_names", return_value=[])
	@patch("retailedge.guided_sales_invoice._validate_transaction_context", return_value=("Demo Company", "Lagos", ""))
	@patch("retailedge.guided_sales_invoice._assert_read_permission")
	@patch("retailedge.guided_sales_invoice._assert_can_create_sales_invoice")
	@patch("retailedge.guided_sales_invoice.frappe.new_doc")
	def test_create_draft_resolves_blank_rate_from_server_price_list(
		self,
		mock_new_doc,
		_mock_create_permission,
		mock_read_permission,
		_mock_context,
		_mock_branches,
		_mock_settings,
		mock_price_context,
		mock_item_pricing,
	):
		doc = _DraftSalesInvoice()
		mock_new_doc.return_value = doc
		mock_price_context.return_value = {
			"price_list": "Retail Selling",
			"source": "user_default",
			"allow_rate_change": True,
		}
		mock_item_pricing.side_effect = [
			{"rate": 900.0, "source": "user_default", "allow_rate_change": True},
			{"rate": 1400.0, "source": "user_default", "allow_rate_change": True},
		]

		result = create_simple_sales_invoice_draft(
			{
				"company": "Demo Company",
				"branch": "Lagos",
				"customer": "CUST-001",
				"posting_date": "2026-08-15",
				"update_stock": 0,
				"remarks": "Guided draft",
				"items": [
					{"item_code": "ITEM-001", "qty": 2, "rate": ""},
					{"item_code": "ITEM-002", "qty": 1, "rate": 1500},
				],
			}
		)

		mock_new_doc.assert_called_once_with("Sales Invoice")
		self.assertGreaterEqual(mock_read_permission.call_count, 3)
		self.assertEqual(doc.insert_calls, 1)
		self.assertEqual(doc.company, "Demo Company")
		self.assertEqual(doc.customer, "CUST-001")
		self.assertEqual(doc.branch, "Lagos")
		self.assertEqual(doc.selling_price_list, "Retail Selling")
		self.assertEqual(str(doc.posting_date), "2026-08-15")
		self.assertEqual(doc.remarks, "Guided draft")
		self.assertEqual(len(doc.items), 2)
		self.assertEqual(doc.items[0].rate, 900.0)
		self.assertEqual(doc.items[1].rate, 1500.0)
		self.assertEqual(result["name"], doc.name)
		self.assertEqual(result["docstatus"], 0)
		self.assertEqual(result["selling_price_list"], "Retail Selling")

	@patch("retailedge.guided_sales_invoice.resolve_sales_item_pricing")
	@patch("retailedge.guided_sales_invoice.resolve_price_list_context")
	@patch("retailedge.guided_sales_invoice.get_retailedge_settings", return_value=SimpleNamespace(allow_guided_sales_update_stock_edit=1))
	@patch("retailedge.guided_sales_invoice.get_guided_branch_names", return_value=[])
	@patch("retailedge.guided_sales_invoice._validate_transaction_context", return_value=("Demo Company", "", ""))
	@patch("retailedge.guided_sales_invoice._assert_read_permission")
	@patch("retailedge.guided_sales_invoice._assert_can_create_sales_invoice")
	@patch("retailedge.guided_sales_invoice.frappe.new_doc")
	def test_pos_profile_rate_lock_ignores_browser_rate_override(
		self,
		mock_new_doc,
		_mock_create_permission,
		_mock_read_permission,
		_mock_context,
		_mock_branches,
		_mock_settings,
		mock_price_context,
		mock_item_pricing,
	):
		doc = _DraftSalesInvoice()
		mock_new_doc.return_value = doc
		mock_price_context.return_value = {
			"price_list": "POS Retail",
			"source": "pos_profile",
			"allow_rate_change": False,
		}
		mock_item_pricing.return_value = {
			"rate": 1200.0,
			"source": "pos_profile",
			"allow_rate_change": False,
		}

		create_simple_sales_invoice_draft(
			{
				"company": "Demo Company",
				"customer": "CUST-001",
				"items": [{"item_code": "ITEM-001", "qty": 1, "rate": 1}],
			}
		)
		self.assertEqual(doc.items[0].rate, 1200.0)

	def test_adapter_uses_permission_aware_bounded_search_and_draft_insert(self):
		source = (APP_ROOT / "guided_sales_invoice.py").read_text()
		self.assertIn("search_link(", source)
		self.assertIn("MAX_LINK_RESULTS = 20", source)
		self.assertIn("min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS)", source)
		self.assertIn('query="erpnext.controllers.queries.item_query"', source)
		self.assertIn('filters: dict[str, Any] = {"is_sales_item": 1}', source)
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn("doc.insert()", source)
		self.assertIn("doc.branch = branch", source)
		self.assertIn("resolve_sales_item_pricing", source)
		self.assertIn("doc.selling_price_list", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("doc.submit()", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_browser_price_list_choice_is_revalidated_by_server_governance(self):
		source = (APP_ROOT / "guided_sales_invoice.py").read_text()
		self.assertIn("resolve_price_list_context", source)
		self.assertNotIn('values.get("selling_price_list")', source)
		self.assertIn('selected_price_list=str(values.get("price_list") or "").strip()', source)
		self.assertIn("search_allowed_price_lists", source)

	def test_adapter_leaves_accounting_and_pricing_rules_to_erpnext(self):
		source = (APP_ROOT / "guided_sales_invoice.py").read_text()
		self.assertNotIn("calculate_taxes_and_totals()", source)
		self.assertNotIn("debit_to =", source)
		self.assertNotIn("income_account", source)
		self.assertNotIn("taxes_and_charges =", source)
		self.assertNotIn("payment_schedule", source)
		self.assertIn("resolve_sales_item_pricing", source)

	def test_guided_dialog_uses_shared_edgesuite_components_and_multiple_item_rows(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimpleSalesInvoiceDialog.vue"
		).read_text()
		self.assertIn("EdgeModal: runtimeComponents.EdgeModal", component)
		self.assertIn("EdgeLinkField: runtimeComponents.EdgeLinkField", component)
		self.assertIn("EdgeChildTable: runtimeComponents.EdgeChildTable", component)
		self.assertIn('fieldname: "item_code"', component)
		self.assertIn('fieldname: "qty"', component)
		self.assertIn('fieldname: "rate"', component)
		self.assertIn("Add Item", component)
		self.assertIn("searchLineLink", component)
		self.assertIn("get_simple_sales_invoice_item_pricing", component)
		self.assertIn("pricingCache: new Map()", component)
		self.assertIn("Selling Price List", component)
		self.assertNotIn("frappe.get_list", component)
		self.assertNotIn("frappe.client.get_list", component)

	def test_guided_dialog_cascades_customer_branch_and_pricing_changes(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimpleSalesInvoiceDialog.vue"
		).read_text()
		self.assertIn("setCustomer(next)", component)
		self.assertIn("setBranch(next)", component)
		self.assertIn("setWarehouse(next)", component)
		self.assertIn("refreshAllItemPricing", component)
		self.assertIn("loadItemPricing(index)", component)
		self.assertIn('this.values.warehouse = "";', component)
		self.assertIn("customer: this.values.customer", component)
		self.assertIn("branch: this.values.branch", component)

	def test_guided_dialog_saves_draft_via_server_adapter_and_keeps_full_form_fallback(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimpleSalesInvoiceDialog.vue"
		).read_text()
		self.assertIn("retailedge.guided_sales_invoice.create_simple_sales_invoice_draft", component)
		self.assertIn("retailedge.guided_sales_invoice.search_simple_sales_invoice_options", component)
		self.assertIn("Advanced: Open in ERPNext", component)
		self.assertIn('this.$emit("open-native", "Sales Invoice")', component)
		self.assertNotIn("frappe.new_doc", component)
		self.assertNotIn("frappe.db.insert", component)

	def test_make_sale_update_stock_defaults_on_and_is_settings_controlled(self):
		backend = (APP_ROOT / "guided_sales_invoice.py").read_text()
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimpleSalesInvoiceDialog.vue"
		).read_text()
		settings = (
			APP_ROOT
			/ "retailedge"
			/ "doctype"
			/ "retailedge_settings"
			/ "retailedge_settings.json"
		).read_text()
		self.assertIn('"update_stock": 1', backend)
		self.assertIn("allow_guided_sales_update_stock_edit", backend)
		self.assertIn("else 1", backend)
		self.assertIn("update_stock: 1", component)
		self.assertIn(':disabled="!canEditUpdateStock"', component)
		self.assertIn("transactionContextReady()", component)
		self.assertIn("requiresBranchSelection()", component)
		self.assertIn('"fieldname": "allow_guided_sales_update_stock_edit"', settings)
		self.assertIn('"default": "0"', settings)

	def test_make_sale_branch_and_stock_location_are_ui_gated_before_save(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimpleSalesInvoiceDialog.vue"
		).read_text()
		self.assertIn("Only enabled Branch Setup entries for the active Company are shown.", component)
		self.assertIn(':disabled="requiresBranchSelection && !values.branch"', component)
		self.assertIn(':disabled="saving || loading || !transactionContextReady || quickEntryTooLarge"', component)
		self.assertIn("Choose a Branch before selecting the Stock Location.", component)

	def test_limits_are_deliberately_small_for_guided_entry(self):
		self.assertEqual(MAX_LINK_RESULTS, 20)
		self.assertEqual(MAX_ITEMS, 100)


if __name__ == "__main__":
	unittest.main()
