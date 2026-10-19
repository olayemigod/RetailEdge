from __future__ import annotations

from uuid import uuid4

import frappe
from frappe.utils import add_days, nowdate

import erpnext
from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice
from erpnext.buying.doctype.supplier.test_supplier import create_supplier
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
from erpnext.tests.utils import ERPNextTestSuite

from retailedge import stock_accounting_integrity, supplier_payables

COMPANY = "_Test Company"
STOCK_ITEM = "_Test Item"
STOCK_WAREHOUSE = "_Test Warehouse - _TC"


class TestQARuntimeSupplierStockAcceptance(ERPNextTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		self.load_test_records("Purchase Invoice")
		self.load_test_records("Stock Entry")

	def _make_supplier(self) -> str:
		supplier = create_supplier(supplier_name=f"RetailEdge QA Supplier {uuid4().hex[:8]}")
		return str(supplier.name)

	def _make_open_purchase_invoice(self, *, supplier: str, rate: float, sequence: int) -> str:
		invoice = make_purchase_invoice(
			supplier=supplier,
			qty=1,
			rate=rate,
			do_not_save=True,
		)
		invoice.posting_date = nowdate()
		invoice.due_date = add_days(nowdate(), 14 + sequence)
		invoice.bill_no = f"RE-QA-{uuid4().hex[:10].upper()}"
		invoice.bill_date = nowdate()
		invoice.submit()
		self.assertGreater(float(invoice.outstanding_amount or 0), 0)
		return str(invoice.name)

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
		erpnext.set_perpetual_inventory(1, COMPANY)
		stock_entry = make_stock_entry(
			item_code=STOCK_ITEM,
			to_warehouse=STOCK_WAREHOUSE,
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
