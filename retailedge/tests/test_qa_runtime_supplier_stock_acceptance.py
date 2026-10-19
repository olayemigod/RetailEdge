from __future__ import annotations

from uuid import uuid4

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, cint, nowdate

from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

from retailedge import stock_accounting_integrity, supplier_payables
from retailedge.tests.upgrade_validation_fixture import (
	COMPANY,
	ITEM,
	ITEM_GROUP,
	_ensure_company,
	_ensure_fiscal_year,
	_ensure_item,
	_ensure_transaction_masters,
	_ensure_tree_master,
	_first_cost_center,
	_first_leaf_account,
)

SUPPLIER_GROUP = "RetailEdge QA Suppliers"


class TestQARuntimeSupplierStockAcceptance(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = _ensure_company()
		_ensure_fiscal_year(COMPANY)
		_ensure_transaction_masters()
		_ensure_item()

	def _ensure_supplier_group(self) -> None:
		_ensure_tree_master(
			"Supplier Group",
			"supplier_group_name",
			"All Supplier Groups",
			SUPPLIER_GROUP,
			"parent_supplier_group",
		)

	def _make_supplier(self) -> str:
		self._ensure_supplier_group()
		name = f"RetailEdge QA Supplier {uuid4().hex[:8]}"
		supplier = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": name,
				"supplier_group": SUPPLIER_GROUP,
				"supplier_type": "Company",
			}
		).insert()
		return str(supplier.name)

	def _make_purchase_invoice(self, *, supplier: str, rate: float, sequence: int) -> str:
		payable = _first_leaf_account(COMPANY, root_type="Liability", account_type="Payable")
		expense = _first_leaf_account(COMPANY, root_type="Expense")
		cost_center = _first_cost_center(COMPANY)
		invoice = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"company": COMPANY,
				"supplier": supplier,
				"posting_date": nowdate(),
				"due_date": add_days(nowdate(), 14 + sequence),
				"bill_no": f"RE-QA-{uuid4().hex[:10].upper()}",
				"bill_date": nowdate(),
				"currency": self.company.default_currency or "NGN",
				"conversion_rate": 1,
				"credit_to": payable,
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": rate,
						"expense_account": expense,
						"cost_center": cost_center,
					}
				],
			}
		)
		invoice.insert()
		invoice.submit()
		self.assertGreater(float(invoice.outstanding_amount or 0), 0)
		return str(invoice.name)

	def _ensure_perpetual_inventory(self) -> None:
		company = frappe.get_doc("Company", COMPANY)
		if company.meta.has_field("enable_perpetual_inventory") and not cint(company.enable_perpetual_inventory):
			company.enable_perpetual_inventory = 1
			company.save()

	def _make_stock_warehouse(self) -> str:
		parent = frappe.db.get_value(
			"Warehouse",
			{"company": COMPANY, "is_group": 1},
			"name",
			order_by="lft asc",
		)
		self.assertTrue(parent, f"No Warehouse root exists for {COMPANY}.")
		warehouse = frappe.get_doc(
			{
				"doctype": "Warehouse",
				"warehouse_name": f"RetailEdge QA Runtime Stock {uuid4().hex[:8]}",
				"company": COMPANY,
				"parent_warehouse": parent,
				"is_group": 0,
				"disabled": 0,
			}
		).insert()
		return str(warehouse.name)

	def _make_stock_item(self) -> str:
		item_code = f"RE-QA-STOCK-{uuid4().hex[:10].upper()}"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": ITEM_GROUP,
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert()
		return item_code

	def test_supplier_payables_keeps_two_open_invoices_for_one_supplier(self):
		supplier = self._make_supplier()
		invoice_names = {
			self._make_purchase_invoice(supplier=supplier, rate=700, sequence=1),
			self._make_purchase_invoice(supplier=supplier, rate=900, sequence=2),
		}

		result = supplier_payables.get_supplier_payables(
			filters={
				"company": COMPANY,
				"as_of_date": nowdate(),
				"supplier": supplier,
				"ageing_bucket": "All",
				"overdue_only": 0,
			},
			page=1,
			page_size=25,
		)

		rows = list(result.get("rows") or [])
		self.assertEqual(result.get("balance_basis"), "current_outstanding")
		self.assertEqual(result.get("pagination", {}).get("total_rows"), 2)
		self.assertEqual(len(rows), 2)
		self.assertEqual({row.get("invoice") for row in rows}, invoice_names)
		self.assertEqual({row.get("supplier") for row in rows}, {supplier})
		self.assertTrue(all(float(row.get("outstanding") or 0) > 0 for row in rows))

		summary = {row.get("label"): row.get("value") for row in result.get("summary") or []}
		self.assertEqual(summary.get("Open Bills"), 2)

	def test_stock_accounting_integrity_completes_against_native_erpnext_data(self):
		self._ensure_perpetual_inventory()
		warehouse = self._make_stock_warehouse()
		item_code = self._make_stock_item()
		stock_entry = make_stock_entry(
			item_code=item_code,
			to_warehouse=warehouse,
			qty=2,
			rate=100,
			company=COMPANY,
		)

		self.assertTrue(
			frappe.db.exists(
				"Stock Ledger Entry",
				{"voucher_type": "Stock Entry", "voucher_no": stock_entry.name, "is_cancelled": 0},
			)
		)
		self.assertTrue(
			frappe.db.exists(
				"GL Entry",
				{"voucher_type": "Stock Entry", "voucher_no": stock_entry.name, "is_cancelled": 0},
			)
		)

		result = stock_accounting_integrity.get_stock_accounting_integrity(
			filters={
				"company": COMPANY,
				"from_date": add_days(nowdate(), -7),
				"as_on_date": nowdate(),
			},
			page=1,
			page_size=25,
		)

		self.assertEqual(result.get("native_report_name"), "Stock and Account Value Comparison")
		self.assertEqual(result.get("read_only"), 1)
		self.assertEqual(result.get("scope", {}).get("company"), COMPANY)
		self.assertIsInstance(result.get("rows"), list)
		self.assertIn("pagination", result)
		self.assertIn("scan", result)
