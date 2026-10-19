from __future__ import annotations

from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime, nowdate

from retailedge.pos_runtime import get_pos_runtime_capabilities
from retailedge.retailedge.report.retailedge_cash_shift_verification.retailedge_cash_shift_verification import (
	get_columns,
)
from retailedge.shift_reconciliation_completeness import (
	AUDIT_REQUIRED_STATUS,
	_get_scoped_closing_shifts,
	augment_shift_reconciliation_rows,
)
from retailedge.tests.upgrade_validation_fixture import (
	COMPANY,
	_ensure_company,
	_ensure_fiscal_year,
	_ensure_transaction_masters,
)


class TestShiftReconciliationNativePosRuntime(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		_ensure_company()
		_ensure_fiscal_year(COMPANY)
		_ensure_transaction_masters()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")

	def test_native_erpnext_closing_entry_is_included_with_truthful_cash_reconciliation(self):
		runtime = get_pos_runtime_capabilities()
		if runtime.provider != "erpnext":
			self.skipTest("This acceptance targets the native ERPNext POS fallback runtime.")

		self.assertEqual(runtime.opening_doctype, "POS Opening Entry")
		self.assertEqual(runtime.closing_doctype, "POS Closing Entry")

		columns = {column.get("fieldname"): column for column in get_columns()}
		self.assertEqual(columns["opening_shift"].get("options"), "POS Opening Entry")
		self.assertEqual(columns["closing_shift"].get("options"), "POS Closing Entry")

		cash_mode = f"RetailEdge QA Cash {uuid4().hex[:8]}"
		frappe.get_doc(
			{
				"doctype": "Mode of Payment",
				"name": cash_mode,
				"mode_of_payment": cash_mode,
				"type": "Cash",
				"enabled": 1,
			}
		).db_insert()

		opening_name = f"POS-OPE-QA-{uuid4().hex[:10].upper()}"
		opening = frappe.get_doc(
			{
				"doctype": "POS Opening Entry",
				"name": opening_name,
				"docstatus": 1,
				"status": "Closed",
				"period_start_date": now_datetime(),
				"posting_date": nowdate(),
				"company": COMPANY,
				"user": "Administrator",
			}
		)
		opening.db_insert()
		frappe.get_doc(
			{
				"doctype": "POS Opening Entry Detail",
				"name": f"POS-OPE-DTL-QA-{uuid4().hex[:10].upper()}",
				"parent": opening_name,
				"parenttype": "POS Opening Entry",
				"parentfield": "balance_details",
				"idx": 1,
				"mode_of_payment": cash_mode,
				"opening_amount": 1000,
			}
		).db_insert()

		closing_name = f"POS-CLO-QA-{uuid4().hex[:10].upper()}"
		closing = frappe.get_doc(
			{
				"doctype": "POS Closing Entry",
				"name": closing_name,
				"docstatus": 1,
				"status": "Submitted",
				"period_start_date": opening.period_start_date,
				"period_end_date": now_datetime(),
				"posting_date": nowdate(),
				"posting_time": "12:00:00",
				"company": COMPANY,
				"user": "Administrator",
				"pos_opening_entry": opening_name,
			}
		)
		closing.db_insert()
		frappe.get_doc(
			{
				"doctype": "POS Closing Entry Detail",
				"name": f"POS-CLO-DTL-QA-{uuid4().hex[:10].upper()}",
				"parent": closing_name,
				"parenttype": "POS Closing Entry",
				"parentfield": "payment_reconciliation",
				"idx": 1,
				"mode_of_payment": cash_mode,
				"opening_amount": 1000,
				"expected_amount": 1500,
				"closing_amount": 1450,
				"difference": -50,
			}
		).db_insert()

		filters = frappe._dict(
			company=COMPANY,
			from_date=nowdate(),
			to_date=nowdate(),
		)
		rows = _get_scoped_closing_shifts(filters)
		by_name = {row.get("name"): row for row in rows}
		self.assertIn(closing_name, by_name)
		self.assertEqual(by_name[closing_name].get("opening_shift"), opening_name)
		self.assertEqual(by_name[closing_name].get("company"), COMPANY)
		self.assertEqual(by_name[closing_name].get("cashier"), "Administrator")
		self.assertEqual(by_name[closing_name].get("pos_provider"), "erpnext")

		reconciled_rows, completeness = augment_shift_reconciliation_rows([], filters)
		reconciled = {row.get("closing_shift"): row for row in reconciled_rows}
		self.assertIn(closing_name, reconciled)
		row = reconciled[closing_name]
		self.assertEqual(row.get("review_status"), AUDIT_REQUIRED_STATUS)
		self.assertEqual(row.get("audit_required"), 1)
		self.assertEqual(row.get("opening_cash"), 1000)
		self.assertEqual(row.get("cash_sales"), 500)
		self.assertEqual(row.get("expected_cash"), 1500)
		self.assertEqual(row.get("actual_closing_cash"), 1450)
		self.assertEqual(row.get("cash_variance"), -50)
		self.assertEqual(row.get("cash_status"), "Shortage")
		self.assertGreaterEqual(completeness.get("closing_shift_count", 0), 1)
		self.assertGreaterEqual(completeness.get("missing_audit_total", 0), 1)
		self.assertGreaterEqual(completeness.get("missing_audit_visible", 0), 1)
