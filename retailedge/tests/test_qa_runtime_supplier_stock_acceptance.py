from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase
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
STOCK_ITEM = "RE-QA-STOCK-ITEM"
_BRANCH_CACHE_ATTR = "retailedge_branch_attr_target_doctypes"
_MISSING = object()


class TestQARuntimeSupplierStockAcceptance(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		_ensure_company()
		_ensure_fiscal_year(COMPANY)
		_ensure_transaction_masters()
		_ensure_item()
		cls._ensure_supplier_group()
		cls._ensure_stock_entry_type()
		cls._ensure_stock_item()
		cls.stock_warehouse = cls._first_stock_warehouse()

	@classmethod
	def _ensure_supplier_group(cls) -> None:
		_ensure_tree_master(
			"Supplier Group",
			"supplier_group_name",
			"All Supplier Groups",
			SUPPLIER_GROUP,
			"parent_supplier_group",
		)

	@classmethod
	def _ensure_stock_entry_type(cls) -> None:
		if frappe.db.get_value(
			"Stock Entry Type",
			{"purpose": "Material Receipt", "is_standard": 1},
			"name",
		):
			return
		if frappe.db.exists("Stock Entry Type", "Material Receipt"):
			frappe.db.set_value(
				"Stock Entry Type",
				"Material Receipt",
				"is_standard",
				1,
				update_modified=False,
			)
			return
		frappe.get_doc(
			{
				"doctype": "Stock Entry Type",
				"name": "Material Receipt",
				"purpose": "Material Receipt",
				"is_standard": 1,
			}
		).insert()

	@classmethod
	def _ensure_stock_item(cls) -> None:
		if frappe.db.exists("Item", STOCK_ITEM):
			return
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": STOCK_ITEM,
				"item_name": "RetailEdge QA Stock Item",
				"item_group": ITEM_GROUP,
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert()

	@classmethod
	def _first_stock_warehouse(cls) -> str:
		rows = frappe.get_all(
			"Warehouse",
			filters={"company": COMPANY, "is_group": 0, "disabled": 0},
			fields=["name"],
			order_by="name asc",
			limit=1,
		)
		if not rows:
			frappe.throw(f"RetailEdge QA requires a leaf Warehouse for {COMPANY}.")
		return str(rows[0]["name"])

	def setUp(self):
		super().setUp()
		self._original_user = frappe.session.user
		previous = getattr(frappe.local, _BRANCH_CACHE_ATTR, _MISSING)
		self._branch_cache_before_test = list(previous) if isinstance(previous, list) else previous
		frappe.set_user("Administrator")

	def tearDown(self):
		try:
			if self._branch_cache_before_test is _MISSING:
				if hasattr(frappe.local, _BRANCH_CACHE_ATTR):
					delattr(frappe.local, _BRANCH_CACHE_ATTR)
			else:
				setattr(frappe.local, _BRANCH_CACHE_ATTR, self._branch_cache_before_test)
			frappe.set_user(self._original_user)
		finally:
			super().tearDown()

	def _make_supplier(self) -> str:
		supplier = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": f"RetailEdge QA Supplier {uuid4().hex[:8]}",
				"supplier_group": SUPPLIER_GROUP,
				"supplier_type": "Company",
			}
		).insert()
		return str(supplier.name)

	def _make_open_purchase_invoice(self, *, supplier: str, rate: float, sequence: int) -> str:
		company = frappe.get_doc("Company", COMPANY)
		invoice = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"company": COMPANY,
				"supplier": supplier,
				"posting_date": nowdate(),
				"due_date": add_days(nowdate(), 14 + sequence),
				"bill_no": f"RE-QA-{uuid4().hex[:10].upper()}",
				"bill_date": nowdate(),
				"currency": company.default_currency or "NGN",
				"conversion_rate": 1,
				"credit_to": company.default_payable_account
				or _first_leaf_account(COMPANY, root_type="Liability", account_type="Payable"),
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": rate,
						"expense_account": company.default_expense_account
						or _first_leaf_account(COMPANY, root_type="Expense"),
						"cost_center": _first_cost_center(COMPANY),
					}
				],
			}
		)
		invoice.insert()
		invoice.submit()
		self.assertGreater(float(invoice.outstanding_amount or 0), 0)
		return str(invoice.name)

	@contextmanager
	def _temporary_perpetual_inventory(self):
		original_value = cint(frappe.db.get_value("Company", COMPANY, "enable_perpetual_inventory") or 0)
		cache_before = getattr(frappe.local, "enable_perpetual_inventory", _MISSING)
		cache_snapshot = dict(cache_before) if isinstance(cache_before, dict) else cache_before

		frappe.db.set_value("Company", COMPANY, "enable_perpetual_inventory", 1, update_modified=False)
		if not isinstance(getattr(frappe.local, "enable_perpetual_inventory", None), dict):
			frappe.local.enable_perpetual_inventory = {}
		frappe.local.enable_perpetual_inventory[COMPANY] = 1
		try:
			yield
		finally:
			frappe.db.set_value(
				"Company",
				COMPANY,
				"enable_perpetual_inventory",
				original_value,
				update_modified=False,
			)
			if cache_before is _MISSING:
				if hasattr(frappe.local, "enable_perpetual_inventory"):
					delattr(frappe.local, "enable_perpetual_inventory")
			else:
				frappe.local.enable_perpetual_inventory = cache_snapshot

	def test_supplier_payables_keeps_two_open_invoices_for_one_supplier(self):
		supplier = self._make_supplier()
		invoice_names = {
			self._make_open_purchase_invoice(supplier=supplier, rate=700, sequence=1),
			self._make_open_purchase_invoice(supplier=supplier, rate=900, sequence=2),
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
		with self._temporary_perpetual_inventory():
			stock_entry = make_stock_entry(
				item_code=STOCK_ITEM,
				to_warehouse=self.stock_warehouse,
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
