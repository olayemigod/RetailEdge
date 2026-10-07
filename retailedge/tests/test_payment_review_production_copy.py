from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "public/js/retailedge_business_hub/SimplePaymentDialog.vue"


def test_payment_review_hints_use_business_language_and_preserve_posting_authority():
	text = DIALOG.read_text(encoding="utf-8")

	for contract in (
		"Submitting posts the Payment Entry through standard accounting controls.",
		"The payment is applied through the normal posting process; this review does not directly edit the source Sales Invoice/Sales Order or customer balance.",
		"The payment is applied through the normal posting process; this review does not directly edit the Purchase Invoice outstanding amount or supplier balance.",
		"Customer Payment Review",
		"Supplier Payment Review",
		"Payment Entry",
	):
		assert contract in text

	for forbidden in (
		"GL Entry",
		"Payment Ledger Entry",
	):
		assert forbidden not in text

	# The guided review must continue to use the established server-authoritative payment paths.
	for contract in (
		"standard_customer_payment_submit",
		"standard_supplier_payment_submit",
		"apply_standard_customer_payment_workflow_action",
		"apply_standard_supplier_payment_workflow_action",
		"expected_modified",
		"expected_workflow_state",
	):
		assert contract in text

	for forbidden in (
		".docstatus =",
		".workflow_state =",
		".outstanding_amount =",
	):
		assert forbidden not in text
