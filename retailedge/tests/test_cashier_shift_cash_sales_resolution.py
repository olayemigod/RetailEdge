from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from retailedge.cashier_context import get_shift_cash_sales


class _Meta:
	def __init__(self, fields):
		self._fields = set(fields)

	def has_field(self, fieldname):
		return fieldname in self._fields


class TestCashierShiftCashSalesResolution(unittest.TestCase):
	def _window(self):
		return {
			"opening_shift": SimpleNamespace(name="POSA-OS-TEST-0001"),
			"closing_shift": None,
			"company": "Example Company",
			"pos_profile": "Example POS Profile",
			"user": "cashier@example.com",
			"shift_start": None,
			"shift_end": None,
		}

	@staticmethod
	def _find_first_field(doctype, candidates):
		if doctype == "Sales Invoice" and "posa_pos_opening_shift" in candidates:
			return "posa_pos_opening_shift"
		if doctype == "Sales Invoice" and "pos_profile" in candidates:
			return "pos_profile"
		return None

	def test_direct_shift_query_with_no_invoices_resolves_zero_cash_sales(self):
		sales_meta = _Meta({"payments", "is_pos", "company", "posa_pos_opening_shift", "pos_profile"})
		payment_meta = _Meta({"mode_of_payment", "account", "amount", "base_amount"})
		with (
			patch("retailedge.cashier_context._get_shift_window", return_value=self._window()),
			patch("retailedge.cashier_context._has_doctype", return_value=True),
			patch(
				"retailedge.cashier_context.resolve_cash_payment_account",
				return_value={"mode_of_payment": "Cash", "payment_account": "Cash - EC"},
			),
			patch(
				"retailedge.cashier_context.frappe.get_meta",
				side_effect=lambda doctype: sales_meta if doctype == "Sales Invoice" else payment_meta,
			),
			patch("retailedge.cashier_context._find_first_field", side_effect=self._find_first_field),
			patch("retailedge.cashier_context.frappe.get_all", return_value=[]),
			patch(
				"retailedge.cashier_context._get_shift_cash_payment_entries",
				return_value={"cash_sales": 0.0, "matched_payment_count": 0, "message": None},
			),
		):
			result = get_shift_cash_sales(
				opening_shift="POSA-OS-TEST-0001",
				company="Example Company",
				pos_profile="Example POS Profile",
			)

		self.assertEqual(result["cash_sales"], 0.0)
		self.assertEqual(result["matched_invoice_count"], 0)
		self.assertEqual(result["matched_payment_count"], 0)
		self.assertEqual(result["source"], "sales_invoice.posa_pos_opening_shift")
		self.assertIsNone(result["message"])

	def test_direct_shift_query_failure_remains_unresolved(self):
		sales_meta = _Meta({"payments", "is_pos", "company", "posa_pos_opening_shift", "pos_profile"})
		payment_meta = _Meta({"mode_of_payment", "account", "amount", "base_amount"})
		with (
			patch("retailedge.cashier_context._get_shift_window", return_value=self._window()),
			patch("retailedge.cashier_context._has_doctype", return_value=True),
			patch(
				"retailedge.cashier_context.resolve_cash_payment_account",
				return_value={"mode_of_payment": "Cash", "payment_account": "Cash - EC"},
			),
			patch(
				"retailedge.cashier_context.frappe.get_meta",
				side_effect=lambda doctype: sales_meta if doctype == "Sales Invoice" else payment_meta,
			),
			patch("retailedge.cashier_context._find_first_field", side_effect=self._find_first_field),
			patch("retailedge.cashier_context.frappe.get_all", side_effect=Exception("query failed")),
			patch(
				"retailedge.cashier_context._get_shift_cash_payment_entries",
				return_value={"cash_sales": 0.0, "matched_payment_count": 0, "message": None},
			),
		):
			result = get_shift_cash_sales(
				opening_shift="POSA-OS-TEST-0001",
				company="Example Company",
				pos_profile="Example POS Profile",
			)

		self.assertEqual(result["cash_sales"], 0.0)
		self.assertEqual(result["source"], "unresolved")
		self.assertIn("could not be safely resolved", result["message"])


if __name__ == "__main__":
	unittest.main()
