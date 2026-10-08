from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.customer_sales_intelligence import _get_first_purchase_dates


class TestCustomerIntelligenceFrappeV16Aggregate(unittest.TestCase):
	def test_first_purchase_query_uses_structured_min_aggregate(self):
		filters = frappe._dict(company="RetailEdge Consulting", to_date="2026-10-07")
		with (
			patch(
				"retailedge.customer_sales_intelligence._invoice_branch_scope",
				return_value=(None, None),
			),
			patch(
				"retailedge.customer_sales_intelligence.frappe.get_list",
				return_value=[
					frappe._dict(customer="CUST-001", first_purchase_date="2026-01-15")
				],
			) as get_list,
		):
			result = _get_first_purchase_dates(filters, ["CUST-001"])

		self.assertEqual(result, {"CUST-001": "2026-01-15"})
		kwargs = get_list.call_args.kwargs
		self.assertEqual(
			kwargs["fields"],
			["customer", {"MIN": "posting_date", "as": "first_purchase_date"}],
		)
		self.assertFalse(
			any(isinstance(field, str) and "min(" in field.lower() for field in kwargs["fields"])
		)
		self.assertEqual(kwargs["group_by"], "customer")
		self.assertEqual(kwargs["order_by"], "customer asc")


if __name__ == "__main__":
	unittest.main()
