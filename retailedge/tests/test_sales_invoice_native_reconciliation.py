from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.reconciliation_bridge import (
	EXECUTION_STATUS_EXECUTED,
	PREFLIGHT_READY,
	PREFLIGHT_TARGET_AMBIGUOUS,
	TARGET_AMBIGUOUS,
	TARGET_AVAILABLE,
	_execute_native_reconciliation,
	build_reconciliation_preflight,
	resolve_reconciliation_target,
)


class SalesInvoiceNativeReconciliationTests(unittest.TestCase):
	def _match(self, **overrides):
		row = {
			"name": "RE-BTM-SI-0001",
			"bank_transaction": "ACC-BTN-SI-0001",
			"bank_account": "Access Bank Ketu - Access Bank",
			"bank_amount": 155000,
			"suggested_document_type": "Sales Invoice",
			"suggested_document": "ACC-SINV-2026-00004",
			"candidate_doctype": "Sales Invoice",
			"candidate_name": "ACC-SINV-2026-00004",
			"candidate_docstatus": 1,
			"candidate_amount": 155000,
			"amount_difference": 0,
			"payment_event_source": "Invoice Payment Row",
			"payment_event_amount": 155000,
			"payment_account": "Bank - RC",
			"resolved_bank_account": "Bank - RC",
			"resolved_payment_account": "Bank - RC",
			"account_resolution_status": "match",
			"decision_status": "Confirmed",
			"review_status": "Confirmed",
			"reconciliation_readiness_status": "Ready for Reconciliation",
			"handoff_status": "Ready for ERPNext Reconciliation",
			"details_json": json.dumps({"candidate_context": {"payment_row_index": 1}}),
		}
		row.update(overrides)
		return frappe._dict(row)

	def _single_bank_row(self):
		return {
			"payment_row_index": 1,
			"mode_of_payment": "Bank Draft",
			"account": "Bank - RC",
			"amount": 155000,
			"base_amount": 155000,
			"payment_category": "Bank Transfer",
		}

	@patch("retailedge.reconciliation_bridge.get_payment_entries_for_sales_invoice", return_value=[])
	@patch("retailedge.reconciliation_bridge.get_sales_invoice_payment_rows")
	@patch("retailedge.reconciliation_bridge.frappe.get_doc")
	def test_unique_invoice_payment_row_is_native_target(self, get_doc, get_rows, _get_entries):
		get_doc.return_value = SimpleNamespace(docstatus=1, payments=[object()])
		get_rows.return_value = [self._single_bank_row()]

		target = resolve_reconciliation_target(self._match())

		self.assertEqual(target["target_status"], TARGET_AVAILABLE)
		self.assertEqual(target["erpnext_target_doctype"], "Sales Invoice")
		self.assertEqual(target["erpnext_target_name"], "ACC-SINV-2026-00004")

	@patch("retailedge.reconciliation_bridge.get_payment_entries_for_sales_invoice", return_value=[])
	@patch("retailedge.reconciliation_bridge.get_sales_invoice_payment_rows")
	@patch("retailedge.reconciliation_bridge.frappe.get_doc")
	def test_multiple_invoice_payment_rows_fail_closed(self, get_doc, get_rows, _get_entries):
		get_doc.return_value = SimpleNamespace(docstatus=1, payments=[object(), object()])
		get_rows.return_value = [
			self._single_bank_row(),
			{
				"payment_row_index": 2,
				"mode_of_payment": "Cash",
				"account": "Cash - RC",
				"amount": 5000,
				"base_amount": 5000,
				"payment_category": "Cash",
			},
		]

		target = resolve_reconciliation_target(self._match())

		self.assertEqual(target["target_status"], TARGET_AMBIGUOUS)
		self.assertIn("multiple payment rows", target["blocking_reason"].lower())

	@patch("retailedge.reconciliation_bridge.get_payment_entries_for_sales_invoice")
	@patch("retailedge.reconciliation_bridge.get_sales_invoice_payment_rows")
	@patch("retailedge.reconciliation_bridge.frappe.get_doc")
	def test_competing_payment_entry_fails_closed(self, get_doc, get_rows, get_entries):
		get_doc.return_value = SimpleNamespace(docstatus=1, payments=[object()])
		get_rows.return_value = [self._single_bank_row()]
		get_entries.return_value = [{"payment_entry": "ACC-PAY-0001", "docstatus": 1}]

		target = resolve_reconciliation_target(self._match())

		self.assertEqual(target["target_status"], TARGET_AMBIGUOUS)
		self.assertIn("payment entry", target["blocking_reason"].lower())

	@patch("retailedge.reconciliation_bridge.get_payment_entries_for_sales_invoice", return_value=[])
	@patch("retailedge.reconciliation_bridge.get_sales_invoice_payment_rows")
	@patch("retailedge.reconciliation_bridge.frappe.get_doc")
	def test_safe_sales_invoice_preflight_is_ready(self, get_doc, get_rows, _get_entries):
		get_doc.return_value = SimpleNamespace(docstatus=1, payments=[object()])
		get_rows.return_value = [self._single_bank_row()]

		preflight = build_reconciliation_preflight(self._match())

		self.assertEqual(preflight["status"], PREFLIGHT_READY)
		self.assertTrue(preflight["native_execution_supported"])

	@patch("retailedge.reconciliation_bridge.get_payment_entries_for_sales_invoice", return_value=[])
	@patch("retailedge.reconciliation_bridge.get_sales_invoice_payment_rows")
	@patch("retailedge.reconciliation_bridge.frappe.get_doc")
	def test_ambiguous_sales_invoice_preflight_stays_blocked(self, get_doc, get_rows, _get_entries):
		get_doc.return_value = SimpleNamespace(docstatus=1, payments=[object(), object()])
		get_rows.return_value = [self._single_bank_row(), dict(self._single_bank_row(), payment_row_index=2)]

		preflight = build_reconciliation_preflight(self._match())

		self.assertEqual(preflight["status"], PREFLIGHT_TARGET_AMBIGUOUS)
		self.assertFalse(preflight["native_execution_supported"])

	@patch("retailedge.reconciliation_bridge._bank_transaction_link_state")
	@patch("retailedge.reconciliation_bridge.frappe.get_attr")
	def test_native_executor_accepts_sales_invoice_target(self, get_attr, link_state):
		link_state.side_effect = [
			{"state": "ready", "links": []},
			{"state": "already_handled", "links": []},
		]
		native = get_attr.return_value
		dry_run = {
			"erpnext_target_doctype": "Sales Invoice",
			"erpnext_target_name": "ACC-SINV-2026-00004",
			"candidate_doctype": "Sales Invoice",
			"candidate_name": "ACC-SINV-2026-00004",
			"bank_transaction": "ACC-BTN-SI-0001",
			"candidate_amount": 155000,
			"bank_amount": 155000,
			"payment_event_source": "Invoice Payment Row",
		}

		result = _execute_native_reconciliation(self._match(), dry_run)

		self.assertEqual(result["execution_status"], EXECUTION_STATUS_EXECUTED)
		native.assert_called_once()
		args = native.call_args.args
		self.assertEqual(args[0], "ACC-BTN-SI-0001")
		self.assertEqual(json.loads(args[1]), [{"payment_doctype": "Sales Invoice", "payment_name": "ACC-SINV-2026-00004"}])


if __name__ == "__main__":
	unittest.main()
