from unittest import TestCase
from unittest.mock import patch

import frappe

from retailedge.cash_deposit_register import list_cash_deposits


class TestCashDepositRegister(TestCase):
	@patch("retailedge.cash_deposit_register.frappe.has_permission", return_value=True)
	@patch("retailedge.cash_deposit_register._scope", return_value=("Co", "Abuja", True))
	@patch("retailedge.cash_deposit_register.frappe.get_list", return_value=[])
	def test_cashier_list_requires_native_read_and_own_deposits(self, get_list, _scope, _permission):
		result = list_cash_deposits(docstatus="all")
		filters = get_list.call_args.kwargs["filters"]
		self.assertEqual(filters["company"], "Co")
		self.assertEqual(filters["retailedge_branch"], "Abuja")
		self.assertEqual(filters["retailedge_cashier"], frappe.session.user)
		self.assertEqual(filters["payment_type"], "Internal Transfer")
		self.assertEqual(filters["retailedge_cash_custody_type"], "Cash Deposit")
		self.assertNotIn("docstatus", filters)
		self.assertEqual(result["rows"], [])

	@patch("retailedge.cash_deposit_register.frappe.has_permission", return_value=True)
	@patch("retailedge.cash_deposit_register._scope", return_value=("Co", ["in", ["Abuja", "Awka"]], False))
	@patch("retailedge.cash_deposit_register.frappe.get_list", return_value=[])
	def test_reviewer_keeps_branch_scope_and_selected_status(self, get_list, _scope, _permission):
		list_cash_deposits(docstatus="submitted", from_date="2026-11-01", to_date="2026-11-27", page=2)
		filters = get_list.call_args.kwargs["filters"]
		self.assertEqual(filters["retailedge_branch"], ["in", ["Abuja", "Awka"]])
		self.assertNotIn("retailedge_cashier", filters)
		self.assertEqual(filters["docstatus"], 1)
		self.assertEqual(filters["posting_date"], ["between", ["2026-11-01", "2026-11-27"]])
		self.assertEqual(get_list.call_args.kwargs["start"], 25)

	@patch("retailedge.cash_deposit_register.frappe.has_permission", return_value=False)
	@patch("retailedge.cash_deposit_register.frappe.get_list")
	def test_no_payment_entry_read_never_queries_deposits(self, get_list, _permission):
		with self.assertRaises(frappe.PermissionError):
			list_cash_deposits()
		get_list.assert_not_called()
