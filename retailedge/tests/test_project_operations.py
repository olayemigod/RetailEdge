from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.project_operations import get_project_funds_context


class TestProjectOperations(unittest.TestCase):
	@patch("retailedge.project_operations._project_company_currency", return_value="NGN")
	@patch("retailedge.project_operations._project_timeline_rows", return_value=[])
	@patch("retailedge.project_operations._project_payment_rows")
	@patch("retailedge.project_operations._assert_read")
	@patch("retailedge.project_operations.frappe.get_doc")
	def test_project_funds_context_uses_project_and_payment_entry_truth(
		self,
		mock_get_doc,
		_mock_read,
		mock_payment_rows,
		_mock_timeline_rows,
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

		self.assertEqual(context["project_cash_in"], 200000)
		self.assertEqual(context["project_cash_out"], 40000)
		self.assertEqual(context["net_project_cash"], 160000)
		self.assertEqual(context["customer_cash_in"], 200000)
		self.assertEqual(context["supplier_cash_out"], 40000)
		self.assertEqual(context["project_cash_in_rows"][0]["party_type"], "Customer")
		self.assertEqual(context["project_cash_out_rows"][0]["party_type"], "Supplier")
		self.assertEqual(context["funds_received"], 200000)
		self.assertEqual(context["funds_paid_out"], 40000)
		self.assertEqual(context["cash_funds_position"], 160000)
		self.assertEqual(context["unallocated_receipts"], 50000)
		self.assertEqual(context["purchase_cost"], 60000)
		self.assertEqual(context["consumed_material_cost"], 20000)
		self.assertEqual(context["timesheet_cost"], 10000)
		self.assertEqual(context["tracked_cost"], 90000)
		self.assertIn("purchase + consumed material + timesheet", context["tracked_cost_basis"])
		self.assertEqual(context["billed_amount"], 300000)
		self.assertEqual(context["source_of_truth"]["project"], "Project")
		self.assertEqual(context["source_of_truth"]["cash"], "Payment Entry")
		self.assertIn("not revenue, expense, profit, or a bank balance", context["source_of_truth"]["cash_policy"])
		self.assertIn("no custom project wallet or shadow ledger", context["source_of_truth"]["ledger_policy"])
		self.assertNotIn("RetailEdge", context["source_of_truth"]["ledger_policy"])
		self.assertEqual(context["scope"]["project_totals"], "Whole Project across all branches")

	@patch("retailedge.project_operations._project_company_currency", return_value="NGN")
	@patch("retailedge.project_operations._project_timeline_rows", return_value=[])
	@patch("retailedge.project_operations._project_payment_rows", return_value=[])
	@patch("retailedge.project_operations._assert_read")
	@patch("retailedge.project_operations.validate_user_branch_access")
	@patch("retailedge.project_operations.frappe.get_doc")
	def test_branch_scope_is_explicitly_limited_to_cash_and_timeline(
		self,
		mock_get_doc,
		_mock_branch_access,
		_mock_read,
		_mock_payment_rows,
		_mock_timeline_rows,
		_mock_currency,
	):
		mock_get_doc.return_value = SimpleNamespace(
			name="PROJ-0001", project_name="Lagos Rollout", status="Open", project_type="Implementation",
			company="Demo Company", customer="CUST-001", cost_center="Main - DC", percent_complete=40,
			expected_start_date="2026-08-01", expected_end_date="2026-10-31", estimated_costing=100000,
			total_sales_amount=500000, total_billed_amount=300000, total_billable_amount=0,
			total_purchase_cost=60000, total_consumed_material_cost=20000, total_costing_amount=10000,
			gross_margin=210000, per_gross_margin=70,
		)
		with patch("retailedge.project_operations._payment_branch_field", return_value="retailedge_branch"):
			context = get_project_funds_context("PROJ-0001", branch="Lagos")

		self.assertEqual(context["scope"]["cash_and_timeline"], "Branch Lagos")
		self.assertIn("Project billing, costing and margin totals remain whole-project values", context["scope"]["branch_scope_note"])

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

	@patch("retailedge.project_operations._branch_field_for", return_value=None)
	@patch("retailedge.project_operations._date_field_for", return_value="posting_date")
	@patch("retailedge.project_operations._has_field")
	@patch("retailedge.project_operations.frappe.has_permission", return_value=True)
	@patch("retailedge.project_operations.frappe.get_list")
	@patch("retailedge.project_operations.frappe.db.exists")
	def test_project_timeline_uses_native_document_filters(
		self,
		mock_exists,
		mock_get_list,
		_mock_permission,
		mock_has_field,
		_mock_date_field,
		_mock_branch_field,
	):
		from retailedge.project_operations import _project_timeline_rows

		mock_exists.side_effect = lambda doctype, name: doctype == "DocType" and name == "Sales Invoice"
		mock_has_field.side_effect = lambda doctype, fieldname: doctype == "Sales Invoice" and fieldname in {
			"project", "posting_date", "status", "company", "customer", "grand_total", "base_grand_total"
		}
		mock_get_list.return_value = [
			frappe._dict(
				name="SINV-0001",
				docstatus=1,
				posting_date="2026-08-20",
				status="Paid",
				company="Demo Company",
				customer="CUST-001",
				grand_total=120000,
				base_grand_total=120000,
			)
		]

		rows = _project_timeline_rows("PROJ-0001")

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["doctype"], "Sales Invoice")
		self.assertEqual(rows[0]["name"], "SINV-0001")
		self.assertEqual(rows[0]["amount"], 120000)
		filters = mock_get_list.call_args.kwargs["filters"]
		self.assertEqual(filters["project"], "PROJ-0001")
		self.assertEqual(filters["docstatus"], ["<", 2])


if __name__ == "__main__":
	unittest.main()
