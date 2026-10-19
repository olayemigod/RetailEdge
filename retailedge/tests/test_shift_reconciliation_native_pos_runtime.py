from __future__ import annotations

from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime, nowdate

from retailedge.pos_runtime import get_pos_runtime_capabilities
from retailedge.shift_reconciliation_completeness import _get_scoped_closing_shifts
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

	def test_native_erpnext_closing_entry_is_included_in_completeness_scan(self):
		runtime = get_pos_runtime_capabilities()
		if runtime.provider != "erpnext":
			self.skipTest("This acceptance targets the native ERPNext POS fallback runtime.")

		self.assertEqual(runtime.opening_doctype, "POS Opening Entry")
		self.assertEqual(runtime.closing_doctype, "POS Closing Entry")

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

		rows = _get_scoped_closing_shifts(
			frappe._dict(
				company=COMPANY,
				from_date=nowdate(),
				to_date=nowdate(),
			)
		)
		by_name = {row.get("name"): row for row in rows}
		self.assertIn(closing_name, by_name)
		self.assertEqual(by_name[closing_name].get("opening_shift"), opening_name)
		self.assertEqual(by_name[closing_name].get("company"), COMPANY)
		self.assertEqual(by_name[closing_name].get("cashier"), "Administrator")
