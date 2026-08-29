from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.guided_payment import (
	MAX_LINK_RESULTS,
	MAX_REFERENCES,
	PAYMENT_INTENTS,
	_normalise_references,
	create_simple_payment_draft,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _DraftPaymentEntry(SimpleNamespace):
	doctype = "Payment Entry"

	def __init__(self):
		super().__init__(
			name="ACC-PAY-GUIDED-0001",
			docstatus=0,
			references=[],
			insert_calls=0,
			unallocated_amount=0,
		)

	def append(self, table, row):
		self.references.append(frappe._dict(row))
		return self.references[-1]

	def insert(self):
		self.insert_calls += 1
		return self


class TestGuidedPayment(unittest.TestCase):
	def test_payment_intents_map_to_native_erpnext_directions(self):
		receive = PAYMENT_INTENTS["receive-customer-payment"]
		pay = PAYMENT_INTENTS["pay-supplier"]
		self.assertEqual(receive["payment_type"], "Receive")
		self.assertEqual(receive["party_type"], "Customer")
		self.assertEqual(receive["reference_doctype"], "Sales Invoice")
		self.assertEqual(pay["payment_type"], "Pay")
		self.assertEqual(pay["party_type"], "Supplier")
		self.assertEqual(pay["reference_doctype"], "Purchase Invoice")

	def test_normalise_references_rejects_missing_duplicate_and_excess_rows(self):
		for rows in (
			[],
			[{"reference_name": "", "allocated_amount": 10}],
			[
				{"reference_name": "SINV-1", "allocated_amount": 10},
				{"reference_name": "SINV-1", "allocated_amount": 5},
			],
			[{"reference_name": f"SINV-{index}", "allocated_amount": 1} for index in range(MAX_REFERENCES + 1)],
		):
			with self.subTest(rows=len(rows)):
				with self.assertRaises(frappe.ValidationError):
					_normalise_references(rows)

	@patch("retailedge.guided_payment.frappe.db.get_value")
	@patch("retailedge.guided_payment._get_reference_snapshot")
	@patch("retailedge.guided_payment.get_simple_payment_mode_details")
	@patch("retailedge.guided_payment.get_party_details")
	@patch("retailedge.guided_payment._assert_read_permission")
	@patch("retailedge.guided_payment.validate_user_branch_access")
	@patch("retailedge.guided_payment._assert_can_create_payment_entry")
	@patch("retailedge.guided_payment.frappe.new_doc")
	def test_receive_customer_payment_assembles_draft_once(
		self,
		mock_new_doc,
		_mock_create_permission,
		mock_branch_access,
		_mock_read_permission,
		mock_party_details,
		mock_mode_details,
		mock_snapshot,
		mock_db_value,
	):
		doc = _DraftPaymentEntry()
		mock_new_doc.return_value = doc
		mock_db_value.side_effect = lambda doctype, name, fieldname, *args, **kwargs: (
			"NGN" if doctype == "Company" and fieldname == "default_currency" else None
		)
		mock_party_details.return_value = frappe._dict(
			party_account="Debtors - DC",
			party_account_currency="NGN",
		)
		mock_mode_details.return_value = {
			"account": "Bank - DC",
			"account_type": "Bank",
			"account_currency": "NGN",
			"reference_required": True,
		}
		mock_snapshot.return_value = {
			"reference_name": "SINV-0001",
			"outstanding_amount": 2000.0,
			"total_amount": 2500.0,
			"due_date": "2026-08-20",
			"branch": "Lagos",
			"currency": "NGN",
		}

		result = create_simple_payment_draft(
			"receive-customer-payment",
			{
				"company": "Demo Company",
				"branch": "Lagos",
				"posting_date": "2026-08-15",
				"party": "CUST-001",
				"mode_of_payment": "Bank Transfer",
				"amount": 1500,
				"reference_no": "TRF-123",
				"reference_date": "2026-08-15",
				"references": [{"reference_name": "SINV-0001", "allocated_amount": 1500}],
			},
		)

		mock_new_doc.assert_called_once_with("Payment Entry")
		mock_branch_access.assert_called_once()
		self.assertEqual(doc.insert_calls, 1)
		self.assertEqual(doc.payment_type, "Receive")
		self.assertEqual(doc.party_type, "Customer")
		self.assertEqual(doc.party, "CUST-001")
		self.assertEqual(doc.paid_from, "Debtors - DC")
		self.assertEqual(doc.paid_to, "Bank - DC")
		self.assertEqual(doc.paid_amount, 1500.0)
		self.assertEqual(doc.received_amount, 1500.0)
		self.assertEqual(doc.reference_no, "TRF-123")
		self.assertEqual(doc.branch, "Lagos")
		self.assertEqual(len(doc.references), 1)
		self.assertEqual(doc.references[0].reference_doctype, "Sales Invoice")
		self.assertEqual(doc.references[0].allocated_amount, 1500.0)
		self.assertEqual(result["docstatus"], 0)
		self.assertEqual(result["name"], doc.name)

	@patch("retailedge.guided_payment.frappe.db.get_value")
	@patch("retailedge.guided_payment._get_reference_snapshot")
	@patch("retailedge.guided_payment.get_simple_payment_mode_details")
	@patch("retailedge.guided_payment.get_party_details")
	@patch("retailedge.guided_payment._assert_read_permission")
	@patch("retailedge.guided_payment.validate_user_branch_access")
	@patch("retailedge.guided_payment._assert_can_create_payment_entry")
	@patch("retailedge.guided_payment.frappe.new_doc")
	def test_pay_supplier_reverses_party_and_bank_account_direction(
		self,
		mock_new_doc,
		_mock_create_permission,
		_mock_branch_access,
		_mock_read_permission,
		mock_party_details,
		mock_mode_details,
		mock_snapshot,
		mock_db_value,
	):
		doc = _DraftPaymentEntry()
		mock_new_doc.return_value = doc
		mock_db_value.side_effect = lambda doctype, name, fieldname, *args, **kwargs: (
			"NGN" if doctype == "Company" and fieldname == "default_currency" else None
		)
		mock_party_details.return_value = frappe._dict(
			party_account="Creditors - DC",
			party_account_currency="NGN",
		)
		mock_mode_details.return_value = {
			"account": "Cash - DC",
			"account_type": "Cash",
			"account_currency": "NGN",
			"reference_required": False,
		}
		mock_snapshot.return_value = {
			"reference_name": "PINV-0001",
			"outstanding_amount": 700.0,
			"total_amount": 700.0,
			"due_date": "2026-08-20",
			"branch": "Lagos",
			"currency": "NGN",
		}

		create_simple_payment_draft(
			"pay-supplier",
			{
				"company": "Demo Company",
				"branch": "Lagos",
				"party": "SUP-001",
				"mode_of_payment": "Cash",
				"amount": 700,
				"references": [{"reference_name": "PINV-0001", "allocated_amount": 700}],
			},
		)

		self.assertEqual(doc.payment_type, "Pay")
		self.assertEqual(doc.party_type, "Supplier")
		self.assertEqual(doc.paid_from, "Cash - DC")
		self.assertEqual(doc.paid_to, "Creditors - DC")
		self.assertFalse(hasattr(doc, "reference_no"))
		self.assertEqual(doc.references[0].reference_doctype, "Purchase Invoice")

	@patch("retailedge.guided_payment.frappe.db.get_value", return_value="NGN")
	@patch("retailedge.guided_payment.get_simple_payment_mode_details")
	@patch("retailedge.guided_payment.get_party_details")
	@patch("retailedge.guided_payment._assert_read_permission")
	@patch("retailedge.guided_payment.validate_user_branch_access")
	@patch("retailedge.guided_payment._assert_can_create_payment_entry")
	def test_multi_currency_payment_is_redirected_to_full_form(
		self,
		_mock_create_permission,
		_mock_branch_access,
		_mock_read_permission,
		mock_party_details,
		mock_mode_details,
		_mock_db_value,
	):
		mock_party_details.return_value = frappe._dict(
			party_account="Debtors USD - DC",
			party_account_currency="USD",
		)
		mock_mode_details.return_value = {
			"account": "Bank - DC",
			"account_type": "Bank",
			"account_currency": "NGN",
			"reference_required": True,
		}
		with self.assertRaises(frappe.ValidationError):
			create_simple_payment_draft(
				"receive-customer-payment",
				{
					"company": "Demo Company",
					"branch": "Lagos",
					"party": "CUST-USD",
					"mode_of_payment": "Bank Transfer",
					"amount": 100,
					"references": [{"reference_name": "SINV-USD", "allocated_amount": 100}],
				},
			)

	def test_adapter_is_bounded_permission_aware_and_draft_only(self):
		source = (APP_ROOT / "guided_payment.py").read_text()
		self.assertIn("MAX_LINK_RESULTS = 20", source)
		self.assertIn("MAX_REFERENCES = 20", source)
		self.assertIn("limit_page_length=limit", source)
		self.assertIn("frappe.get_list(", source)
		self.assertIn("search_link(", source)
		self.assertIn("get_default_bank_cash_account", source)
		self.assertIn("get_party_details", source)
		self.assertIn("get_reference_details", source)
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn("doc.insert()", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("doc.submit()", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_payment_dialog_uses_shared_edgesuite_components_and_cascades_context(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimplePaymentDialog.vue"
		).read_text()
		self.assertIn("EdgeModal: runtimeComponents.EdgeModal", component)
		self.assertIn("EdgeLinkField: runtimeComponents.EdgeLinkField", component)
		self.assertIn("EdgeChildTable: runtimeComponents.EdgeChildTable", component)
		self.assertIn("setParty(next)", component)
		self.assertIn("setBranch(next)", component)
		self.assertIn("setModeOfPayment(next)", component)
		self.assertIn("this.values.references = [emptyReference()]", component)
		self.assertIn('v-if="modeDetails.reference_required"', component)
		self.assertIn("allocatedTotal", component)
		self.assertIn("unallocatedAmount", component)

	def test_payment_dialog_loads_reference_details_on_demand_and_keeps_native_fallback(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimplePaymentDialog.vue"
		).read_text()
		self.assertIn("get_simple_payment_reference_details", component)
		self.assertIn("get_simple_payment_mode_details", component)
		self.assertIn("search_simple_payment_options", component)
		self.assertIn("create_simple_payment_draft", component)
		self.assertIn("Open Full Form", component)
		self.assertIn('this.$emit("open-native", "Payment Entry")', component)
		self.assertNotIn("frappe.get_list", component)
		self.assertNotIn("frappe.db.insert", component)

	def test_limits_are_deliberately_small(self):
		self.assertEqual(MAX_LINK_RESULTS, 20)
		self.assertEqual(MAX_REFERENCES, 20)


if __name__ == "__main__":
	unittest.main()
