from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.guided_purchase_invoice import (
	MAX_ITEMS,
	MAX_LINK_RESULTS,
	_normalise_items,
	_warehouse_search_filters,
	create_simple_purchase_invoice_draft,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _DraftPurchaseInvoice(SimpleNamespace):
	doctype = "Purchase Invoice"

	def __init__(self):
		super().__init__(
			name="ACC-PINV-GUIDED-0001",
			docstatus=0,
			grand_total=5000.0,
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


class TestGuidedPurchaseInvoice(unittest.TestCase):
	def test_normalise_items_keeps_buying_rate_optional_until_server_pricing(self):
		rows = _normalise_items(
			[
				{"item_code": "ITEM-001", "qty": 2, "rate": ""},
				{"item_code": "ITEM-002", "qty": "3", "rate": "2500"},
			]
		)
		self.assertEqual(rows[0], {"item_code": "ITEM-001", "qty": 2.0, "rate": None})
		self.assertEqual(rows[1], {"item_code": "ITEM-002", "qty": 3.0, "rate": 2500.0})

	def test_normalise_items_rejects_invalid_rows(self):
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

	@patch("retailedge.guided_purchase_invoice.has_branch_assignments", return_value=False)
	@patch("retailedge.guided_purchase_invoice.validate_user_branch_access")
	@patch("retailedge.guided_purchase_invoice.get_first_existing_field", return_value="branch")
	@patch("retailedge.guided_purchase_invoice.has_field", return_value=True)
	def test_warehouse_search_filters_company_and_branch(
		self, _mock_has_field, _mock_branch_field, mock_validate_access, _mock_assignments
	):
		filters = _warehouse_search_filters(
			company="Demo Company",
			branch="Lagos",
			user="buyer@example.com",
		)
		self.assertEqual(filters["company"], "Demo Company")
		self.assertEqual(filters["branch"], "Lagos")
		self.assertEqual(filters["is_group"], 0)
		mock_validate_access.assert_called_once()

	@patch("retailedge.guided_purchase_invoice.has_branch_assignments", return_value=False)
	@patch("retailedge.guided_purchase_invoice.resolve_purchase_item_pricing")
	@patch("retailedge.guided_purchase_invoice.resolve_price_list_context")
	@patch("retailedge.guided_purchase_invoice.frappe.db.get_value")
	@patch("retailedge.guided_purchase_invoice._validate_branch_warehouse")
	@patch("retailedge.guided_purchase_invoice._assert_read_permission")
	@patch("retailedge.guided_purchase_invoice.validate_user_branch_access")
	@patch("retailedge.guided_purchase_invoice._assert_can_create_purchase_invoice")
	@patch("retailedge.guided_purchase_invoice.frappe.new_doc")
	def test_create_draft_resolves_blank_buying_rate_before_insert(
		self,
		mock_new_doc,
		_mock_create_permission,
		mock_branch_access,
		_mock_read_permission,
		mock_validate_warehouse,
		mock_db_value,
		mock_price_context,
		mock_item_pricing,
		_mock_assignments,
	):
		doc = _DraftPurchaseInvoice()
		mock_new_doc.return_value = doc
		mock_db_value.return_value = "Demo Company"
		mock_price_context.return_value = {
			"price_list": "Retail Buying",
			"source": "user_default",
		}
		mock_item_pricing.side_effect = [
			{"rate": 1800.0, "source": "user_default"},
			{"rate": 2400.0, "source": "user_default"},
		]

		result = create_simple_purchase_invoice_draft(
			{
				"company": "Demo Company",
				"branch": "Lagos",
				"supplier": "SUP-001",
				"posting_date": "2026-08-15",
				"bill_no": "VENDOR-123",
				"bill_date": "2026-08-14",
				"warehouse": "Lagos Stores - DC",
				"update_stock": 1,
				"remarks": "Guided purchase",
				"items": [
					{"item_code": "ITEM-001", "qty": 2, "rate": ""},
					{"item_code": "ITEM-002", "qty": 1, "rate": 2500},
				],
			}
		)

		mock_new_doc.assert_called_once_with("Purchase Invoice")
		mock_branch_access.assert_called_once()
		mock_validate_warehouse.assert_called_once()
		self.assertEqual(doc.insert_calls, 1)
		self.assertEqual(doc.company, "Demo Company")
		self.assertEqual(doc.supplier, "SUP-001")
		self.assertEqual(doc.branch, "Lagos")
		self.assertEqual(doc.set_warehouse, "Lagos Stores - DC")
		self.assertEqual(doc.buying_price_list, "Retail Buying")
		self.assertEqual(doc.update_stock, 1)
		self.assertEqual(doc.bill_no, "VENDOR-123")
		self.assertEqual(str(doc.bill_date), "2026-08-14")
		self.assertEqual(len(doc.items), 2)
		self.assertEqual(doc.items[0].rate, 1800.0)
		self.assertEqual(doc.items[1].rate, 2500.0)
		self.assertEqual(result["docstatus"], 0)
		self.assertEqual(result["name"], doc.name)
		self.assertEqual(result["buying_price_list"], "Retail Buying")

	@patch(
		"retailedge.guided_purchase_invoice.resolve_operational_branch",
		return_value={"branch": ""},
	)
	@patch("retailedge.guided_purchase_invoice.resolve_purchase_item_pricing")
	@patch("retailedge.guided_purchase_invoice.resolve_price_list_context")
	@patch("retailedge.guided_purchase_invoice._assert_read_permission")
	@patch("retailedge.guided_purchase_invoice._assert_can_create_purchase_invoice")
	@patch("retailedge.guided_purchase_invoice.frappe.new_doc")
	def test_blank_purchase_rate_is_blocked_when_no_price_can_be_resolved(
		self,
		mock_new_doc,
		_mock_create_permission,
		_mock_read_permission,
		mock_price_context,
		mock_item_pricing,
		_mock_resolve_branch,
	):
		mock_new_doc.return_value = _DraftPurchaseInvoice()
		mock_price_context.return_value = {"price_list": "", "source": "item_fallback"}
		mock_item_pricing.return_value = {"rate": None, "source": "item_fallback"}
		with self.assertRaises(frappe.ValidationError):
			create_simple_purchase_invoice_draft(
				{
					"company": "Demo Company",
					"supplier": "SUP-001",
					"items": [{"item_code": "ITEM-001", "qty": 1, "rate": ""}],
				}
			)

	def test_adapter_uses_permission_aware_bounded_search_and_native_draft_insert(self):
		source = (APP_ROOT / "guided_purchase_invoice.py").read_text()
		self.assertIn("MAX_LINK_RESULTS = 20", source)
		self.assertIn("MAX_ITEMS = 50", source)
		self.assertIn("search_link(", source)
		self.assertIn('query="erpnext.controllers.queries.item_query"', source)
		self.assertIn('filters: dict[str, Any] = {"is_purchase_item": 1}', source)
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn("doc.insert()", source)
		self.assertIn("resolve_purchase_item_pricing", source)
		self.assertIn("doc.buying_price_list", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("doc.submit()", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_browser_cannot_supply_the_effective_buying_price_list(self):
		source = (APP_ROOT / "guided_purchase_invoice.py").read_text()
		self.assertIn("resolve_price_list_context", source)
		self.assertNotIn('values.get("buying_price_list")', source)
		self.assertNotIn('values.get("price_list")', source)

	def test_adapter_leaves_accounting_and_pricing_rules_to_erpnext(self):
		source = (APP_ROOT / "guided_purchase_invoice.py").read_text()
		self.assertNotIn("calculate_taxes_and_totals()", source)
		self.assertNotIn("credit_to =", source)
		self.assertNotIn("expense_account", source)
		self.assertNotIn("taxes_and_charges =", source)
		self.assertNotIn("payment_schedule", source)
		self.assertIn("ERPNext's item-pricing service", source)

	def test_dialog_uses_shared_edgesuite_components_and_resolves_buying_price(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimplePurchaseInvoiceDialog.vue"
		).read_text()
		self.assertIn("EdgeModal: runtimeComponents.EdgeModal", component)
		self.assertIn("EdgeLinkField: runtimeComponents.EdgeLinkField", component)
		self.assertIn("EdgeChildTable: runtimeComponents.EdgeChildTable", component)
		self.assertIn("setSupplier(next)", component)
		self.assertIn("setBranch(next)", component)
		self.assertIn("setWarehouse(next)", component)
		self.assertIn("get_simple_purchase_invoice_item_pricing", component)
		self.assertIn("pricingCache: new Map()", component)
		self.assertIn("Buying Price List", component)
		self.assertIn("Buying Rate", component)
		self.assertIn("Supplier Bill No", component)
		self.assertIn("Open Full Form", component)
		self.assertIn('this.$emit("open-native", "Purchase Invoice")', component)

	def test_limits_are_small_for_guided_entry(self):
		self.assertEqual(MAX_LINK_RESULTS, 20)
		self.assertEqual(MAX_ITEMS, 50)


if __name__ == "__main__":
	unittest.main()
