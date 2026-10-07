from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "public/js/retailedge_business_hub/SimplePaymentDialog.vue"


def test_guided_payment_review_uses_business_facing_accounting_copy():
	text = DIALOG.read_text(encoding="utf-8")

	for contract in (
		"Review the draft Payment Entry before posting the customer payment.",
		"Review the draft Payment Entry before posting the supplier payment.",
		"Submitting posts the Payment Entry through standard accounting controls.",
		"The payment and its allocations update customer payment balances as applicable; this review does not edit the source Sales Invoice or Sales Order.",
		"The payment and its allocations update supplier payment balances as applicable; this review does not edit the source Purchase Invoice.",
		"Open Advanced Payment",
	):
		assert contract in text

	for forbidden in (
		"GL Entry",
		"Payment Ledger Entry",
		"Advanced ERPNext",
		"Open in ERPNext",
		"Frappe Workflow",
		"native ERPNext Payment Entry submit flow",
		"ERPNext will post",
	):
		assert forbidden not in text

	# Payment Entry remains the user-facing accounting document; posting/workflow authority stays server-side.
	for contract in (
		"Payment Entry",
		"submit_standard_customer_payment",
		"submit_standard_supplier_payment",
		"apply_standard_customer_payment_workflow_action",
		"apply_standard_supplier_payment_workflow_action",
		"workflow_readiness",
		"expected_modified",
		"expected_workflow_state",
		"window.retailedge?.userErrorMessage",
	):
		assert contract in text

	for forbidden in (
		".workflow_state =",
		".docstatus =",
		".outstanding_amount =",
	):
		assert forbidden not in text
