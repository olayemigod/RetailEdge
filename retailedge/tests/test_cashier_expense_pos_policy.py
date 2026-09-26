from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.pos_cashier_expense import (
	apply_retailedge_cashier_expenses_to_closing_data,
	apply_retailedge_cashier_expenses_to_closing_shift,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestCashierExpensePOSPolicyContract(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_settings_default_to_controlled_and_expose_pos_governance(self):
		doc = json.loads(
			self.read("retailedge/doctype/retailedge_settings/retailedge_settings.json")
		)
		fields = {row["fieldname"]: row for row in doc["fields"]}
		self.assertEqual(fields["cashier_expense_posting_mode"]["default"], "Controlled Posting")
		self.assertEqual(
			fields["cashier_expense_posting_mode"]["options"],
			"Controlled Posting\nDirect Posting",
		)
		self.assertEqual(fields["enable_cashier_expense_pos_integration"]["default"], "0")
		self.assertEqual(fields["show_cashier_expense_in_pos"]["default"], "1")
		self.assertEqual(fields["include_cashier_expenses_in_pos_closing"]["default"], "1")

	def test_cashier_expense_separates_cash_and_accounting_state(self):
		doc = json.loads(
			self.read(
				"retailedge/doctype/retailedge_cashier_expense/retailedge_cashier_expense.json"
			)
		)
		fields = {row["fieldname"]: row for row in doc["fields"]}
		self.assertEqual(fields["cash_movement_status"]["default"], "Not Disbursed")
		self.assertIn("Disbursed", fields["cash_movement_status"]["options"])
		self.assertEqual(fields["cash_source"]["default"], "POS Till")
		self.assertTrue(fields["client_request_id"]["unique"])
		self.assertIn("posting_mode_applied", fields)

	def test_pos_adapter_is_idempotent_and_does_not_trust_client_scope(self):
		source = self.read("pos_cashier_expense.py")
		for contract in (
			'client_request_id = str(values.get("client_request_id")',
			"_get_existing_pos_expense(client_request_id)",
			'doc.entry_source = POS_SOURCE',
			'doc.cash_source = POS_CASH_SOURCE',
			'doc.cash_movement_status = "Disbursed"',
			"doc.submit()",
			"_assert_requested_context_matches(",
		"get_current_cashier_context(user=frappe.session.user)",
		"include_cashier_expenses_in_pos_closing",
			'precision = frappe.get_cached_value("System Settings", None, "currency_precision") or 3',
			'base_expected = flt(cash_row.get("expected_amount"), precision) + flt(previous_total, precision)',
			"cash_row.expected_amount = flt(base_expected - current_total, precision)",
		):
			self.assertIn(contract, source)
		for forbidden in (
			"doc.company =",
			"doc.branch =",
			"doc.cashier =",
			"doc.pos_profile =",
			"doc.payment_account =",
			"doc.expense_account =",
			"ignore_permissions=True",
			"frappe.db.commit()",
		):
			self.assertNotIn(forbidden, source)

	def test_accounting_posting_is_permission_aware_and_single_entry(self):
		source = self.read("cashier_expense_accounting.py")
		for contract in (
			'POSTING_DOCUMENT_TYPE = "Journal Entry"',
			"frappe.has_permission(POSTING_DOCUMENT_TYPE, ptype)",
			"journal.insert()",
			'journal.has_permission("submit")',
			"journal.submit()",
			'"posting_reference": journal.name',
			'"ledger_status": "Posted"',
			'SELECT name FROM `tabRetailEdge Cashier Expense`',
		):
			self.assertIn(contract, source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_pos_closing_hook_and_custom_fields_are_registered(self):
		hooks = self.read("hooks.py")
		self.assertIn(
			"retailedge.pos_cashier_expense.apply_retailedge_cashier_expenses_to_closing_shift",
			hooks,
		)
		self.assertIn(
			"retailedge.pos_cashier_expense.ensure_pos_closing_cashier_expense_custom_fields",
			hooks,
		)

	def test_posnext_closing_preview_override_is_registered(self):
		hooks = self.read("hooks.py")
		self.assertIn(
			'"pos_next.api.shifts.get_closing_shift_data": '
			'"retailedge.pos_cashier_expense.get_posnext_closing_shift_data_with_cashier_expenses"',
			hooks,
		)

	@patch("retailedge.pos_cashier_expense._find_cash_reconciliation_row_from_rows")
	@patch("retailedge.pos_cashier_expense._build_pos_closing_cashier_expense_summary")
	@patch("retailedge.pos_cashier_expense.get_retailedge_settings")
	@patch("retailedge.pos_cashier_expense.frappe.get_meta")
	def test_posnext_closing_preview_reduces_expected_cash_idempotently(
		self,
		mock_meta,
		mock_settings,
		mock_summary,
		mock_cash_row,
	):
		mock_meta.return_value.has_field.return_value = True
		mock_settings.return_value = SimpleNamespace(
			enable_cashier_expense_workflow=1,
			enable_cashier_expense_pos_integration=1,
			include_cashier_expenses_in_pos_closing=1,
		)
		mock_summary.return_value = {
			"total": 150,
			"count": 2,
			"pending_review": 50,
			"pending_ledger": 0,
			"posted": 100,
			"rejected": 0,
		}
		row = {"mode_of_payment": "Cash", "expected_amount": 1100, "closing_amount": None}
		mock_cash_row.return_value = row
		payload = {
			"pos_opening_shift": "OPEN-1",
			"pos_profile": "POS-1",
			"payment_reconciliation": [row],
			"retailedge_cashier_expense_total": 0,
		}

		result = apply_retailedge_cashier_expenses_to_closing_data(
			payload,
			opening_shift="OPEN-1",
		)
		self.assertIs(result, payload)
		self.assertEqual(row["expected_amount"], 950)
		self.assertEqual(payload["retailedge_cashier_expense_total"], 150)
		self.assertEqual(payload["retailedge_cashier_expense_count"], 2)

		apply_retailedge_cashier_expenses_to_closing_data(
			payload,
			opening_shift="OPEN-1",
		)
		self.assertEqual(row["expected_amount"], 950)

	@patch("retailedge.pos_cashier_expense._find_cash_reconciliation_row")
	@patch("retailedge.pos_cashier_expense._build_pos_closing_cashier_expense_summary")
	@patch("retailedge.pos_cashier_expense.get_retailedge_settings")
	@patch("retailedge.pos_cashier_expense.frappe.get_meta")
	def test_closing_adjustment_is_repeat_save_idempotent(
		self,
		mock_meta,
		mock_settings,
		mock_summary,
		mock_cash_row,
	):
		mock_meta.return_value.has_field.return_value = True
		mock_settings.return_value = SimpleNamespace(
			enable_cashier_expense_workflow=1,
			enable_cashier_expense_pos_integration=1,
			include_cashier_expenses_in_pos_closing=1,
		)
		mock_summary.return_value = {
			"total": 150,
			"count": 2,
			"pending_review": 50,
			"pending_ledger": 0,
			"posted": 100,
			"rejected": 0,
		}
		row = frappe._dict(expected_amount=1100, closing_amount=1050)
		mock_cash_row.return_value = row
		doc = SimpleNamespace(
			doctype="POS Closing Shift",
			pos_opening_shift="OPEN-1",
			pos_profile="POS-1",
			retailedge_cashier_expense_total=100,
			retailedge_cashier_expense_count=1,
			retailedge_cashier_expense_note="old",
		)

		apply_retailedge_cashier_expenses_to_closing_shift(doc)
		self.assertEqual(row.expected_amount, 1050)
		self.assertEqual(row.difference, 0)
		self.assertEqual(doc.retailedge_cashier_expense_total, 150)

		apply_retailedge_cashier_expenses_to_closing_shift(doc)
		self.assertEqual(row.expected_amount, 1050)
		self.assertEqual(row.difference, 0)


if __name__ == "__main__":
	unittest.main()
