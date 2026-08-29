from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.advanced_payments import list_customer_advances


class TestAdvancedPaymentBranchSafety(unittest.TestCase):
	@patch("retailedge.advanced_payments._payment_branch_field", return_value=None)
	@patch("retailedge.advanced_payments.validate_user_branch_access")
	@patch("retailedge.advanced_payments._assert_read")
	@patch("retailedge.advanced_payments.frappe.get_list")
	def test_branch_scoped_advance_lookup_fails_closed_without_attribution_field(
		self,
		mock_get_list,
		_mock_assert_read,
		mock_branch_access,
		_mock_branch_field,
	):
		with self.assertRaises(frappe.ValidationError):
			list_customer_advances(
				customer="CUST-001",
				company="Demo Company",
				branch="Lagos",
			)

		mock_branch_access.assert_called_once()
		payment_entry_queries = [
			call for call in mock_get_list.call_args_list
			if call.args and call.args[0] == "Payment Entry"
		]
		self.assertEqual(payment_entry_queries, [])


if __name__ == "__main__":
	unittest.main()
