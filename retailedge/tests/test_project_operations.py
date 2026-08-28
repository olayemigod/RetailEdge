from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.project_operations import get_project_funds_context


class TestProjectOperations(unittest.TestCase):
	@patch("retailedge.project_operations._project_company_currency", return_value="NGN")
	@patch("retailedge.project_operations._project_payment_rows")
	@patch("retailedge.project_operations._assert_read")
	@patch("retailedge.project_operations.frappe.get_doc")
	def test_project_funds_context_uses_project_and_payment_entry_truth(
		self,
		mock_get_doc,
		_mock_read,
		mock_payment_rows,
		_mock_currency,
	):
		mock_get_doc.return_value = SimpleNamespace(
			name="PROJ-0001",
			project_name="Lagos Rollout",
			status="Open",
			project_type="Implementation",
			company="Demo Company",
			customer="CUST-001",
			cost_center="Main - DC",
			percent_complete=40,
			expected_start_date="2026-08-01",
			expected_end_date="2026-10-31",
			estimated_costing=100000,
			total_sales_amount=500000,
			total_billed_amount=300000,
			total_billable_amount=0,
			total_purchase_cost=60000,
			total_consumed_material_cost=20000,
			total_costing_amount=10000,
			gross_margin=210000,
			per_gross_margin=70,
		)
		mock_payment_rows.return_value = [
			frappe._dict(
				name="ACC-PAY-1", posting_date="2026-08-10", payment_type="Receive",
				party_type="Customer", party="CUST-001", company="Demo Company",
				paid_amount=200000, received_amount=200000, base_paid_amount=200000,
				base_received_amount=200000, unallocated_amount=50000,
				mode_of_payment="Bank Transfer", reference_no="TRF-1", reference_date="2026-08-10",
			),
			frappe._dict(
				name="ACC-PAY-2", posting_date="2026-08-12", payment_type="Pay",
				party_type="Supplier", party="SUP-001", company="Demo Company",
				paid_amount=40000, received_amount=40000, base_paid_amount=40000,
				base_received_amount=40000, unallocated_amount=0,
				mode_of_payment="Bank Transfer", reference_no="TRF-2", reference_date="2026-08-12",
			),
		]

		with patch("retailedge.project_operations._payment_branch_field", return_value=None):
			context = get_project_funds_context("PROJ-0001")

		self.assertEqual(context["funds_received"], 200000)
		self.assertEqual(context["funds_paid_out"], 40000)
		self.assertEqual(context["cash_funds_position"], 160000)
		self.assertEqual(context["unallocated_receipts"], 50000)
		self.assertEqual(context["tracked_cost"], 90000)
		self.assertEqual(context["billed_amount"], 300000)
		self.assertEqual(context["source_of_truth"]["project"], "Project")
		self.assertEqual(context["source_of_truth"]["cash"], "Payment Entry")
		self.assertIn("no RetailEdge project wallet", context["source_of_truth"]["ledger_policy"])

	@patch("retailedge.project_operations._payment_branch_field", return_value=None)
	@patch("retailedge.project_operations._assert_read")
	@patch("retailedge.project_operations.validate_user_branch_access")
	def test_branch_scoped_project_payments_fail_closed_without_branch_field(
		self,
		mock_branch_access,
		_mock_read,
		_mock_branch_field,
	):
		from retailedge.project_operations import _project_payment_rows

		with self.assertRaises(frappe.ValidationError):
			_project_payment_rows("PROJ-0001", branch="Lagos")
		mock_branch_access.assert_not_called()


if __name__ == "__main__":
	unittest.main()
