from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.cash_deposit_register import _build_register_filters, list_cash_deposits


class TestCashDepositRegister(unittest.TestCase):
	@patch("retailedge.cash_deposit_register.frappe.session")
	@patch("retailedge.cash_deposit_register.frappe.get_roles", return_value=["RetailEdgeCashier"])
	@patch("retailedge.cash_deposit_register.frappe.has_permission", return_value=True)
	@patch("retailedge.cash_deposit_register.require_cash_custody_fields_installed")
	@patch("retailedge.cash_deposit_register._assert_read_permission")
	@patch("retailedge.cash_deposit_register._resolve_branch_condition", return_value=("retailedge_branch", "Abuja", {}))
	def test_cashier_scope_is_own_deposits_only(self, _branch, _company, _fields, _read, _roles, session):
		session.user = "cashier@example.com"
		filters = _build_register_filters(company="Concepts", branch="Abuja", opening_shift="OPEN-1")
		self.assertEqual(filters["company"], "Concepts")
		self.assertEqual(filters["retailedge_branch"], "Abuja")
		self.assertEqual(filters["retailedge_cashier"], session.user)
		self.assertEqual(filters["retailedge_cash_custody_type"], "Cash Deposit")
		self.assertEqual(filters["payment_type"], "Internal Transfer")
		self.assertEqual(filters["retailedge_pos_opening_shift"], "OPEN-1")
		with self.assertRaises(frappe.PermissionError):
			_build_register_filters(company="Concepts", branch="Abuja", cashier="other@example.com")

	@patch("retailedge.cash_deposit_register.frappe.has_permission", return_value=False)
	def test_native_payment_entry_read_is_required(self, _permission):
		with self.assertRaises(frappe.PermissionError):
			_build_register_filters(company="Concepts")

	@patch("retailedge.cash_deposit_register.frappe.session")
	@patch("retailedge.cash_deposit_register.frappe.get_roles", return_value=["RetailEdgeBranchManager"])
	@patch("retailedge.cash_deposit_register.frappe.has_permission", return_value=True)
	@patch("retailedge.cash_deposit_register.require_cash_custody_fields_installed")
	@patch("retailedge.cash_deposit_register._assert_read_permission")
	@patch("retailedge.cash_deposit_register._resolve_branch_condition", return_value=("retailedge_branch", ["in", ["Abuja", "Lagos"]], {}))
	def test_manager_scope_intersects_native_and_branch_authority(self, branch, _company, _fields, _read, _roles, session):
		session.user = "manager@example.com"
		filters = _build_register_filters(company="Concepts", cashier="cashier@example.com", bank_account="Bank-1", docstatus="draft")
		self.assertEqual(filters["retailedge_branch"], ["in", ["Abuja", "Lagos"]])
		self.assertEqual(filters["retailedge_cashier"], "cashier@example.com")
		self.assertEqual(filters["bank_account"], "Bank-1")
		self.assertEqual(filters["docstatus"], 0)
		branch.return_value = ("retailedge_branch", "__never__", {})
		filters = _build_register_filters(company="Concepts")
		self.assertEqual(filters["retailedge_branch"], "__never__")

	@patch("retailedge.cash_deposit_register._build_register_filters", return_value={"company": "Concepts", "payment_type": "Internal Transfer", "retailedge_cash_custody_type": "Cash Deposit"})
	@patch("retailedge.cash_deposit_register.frappe.get_list")
	def test_pagination_does_not_cap_state_totals(self, get_list, _scope):
		get_list.side_effect = [
			[frappe._dict(name="DEP-1", docstatus=1), frappe._dict(name="DEP-2", docstatus=0)],
			[
				frappe._dict(docstatus=0, currency="NGN", count=3, amount=6000),
				frappe._dict(docstatus=1, currency="NGN", count=1, amount=2000),
			],
		]
		result = list_cash_deposits(company="Concepts", page_size=1)
		self.assertEqual(len(result["rows"]), 1)
		self.assertTrue(result["pagination"]["has_next"])
		self.assertEqual(result["totals"]["draft"], [{"currency": "NGN", "count": 3, "amount": 6000.0}])
		self.assertEqual(result["totals"]["submitted"], [{"currency": "NGN", "count": 1, "amount": 2000.0}])
		self.assertEqual(get_list.call_args_list[0].kwargs["filters"], get_list.call_args_list[1].kwargs["filters"])
