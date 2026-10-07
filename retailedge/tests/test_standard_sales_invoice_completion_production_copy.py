from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "public/js/professional_selling/StandardSalesInvoiceCompletionDialog.vue"


def test_sales_invoice_completion_uses_business_facing_copy_and_preserves_accounting_authority():
	text = DIALOG.read_text(encoding="utf-8")

	# Keep the visible completion surface business-facing for invoices and returns.
	for contract in (
		"Review the saved Sales Invoice and submit it, or continue through the active approval workflow.",
		"Review the submitted Sales Invoice and continue with any permitted next step.",
		"Default price list",
		"Branch and Stock Location validation runs again when draft changes are saved.",
		"Taxes, totals, source quantity limits and accounting checks are recalculated when the draft is saved.",
		"This Credit Note will reduce the outstanding balance of the source invoice when submitted.",
		"The credit will remain on this Credit Note for later reconciliation or refund. The source invoice itself is not changed.",
		"Completion needs attention",
		"Approval workflow",
		"Active approval workflow",
		"No Stock Location",
		"Use output actions or close this review.",
	):
		assert contract in text

	for forbidden in (
		"ERPNext default",
		"ERPNext and Branch/Stock Location",
		"ERPNext recalculates",
		"ERPNext will submit",
		"ERPNext will keep",
		"Frappe Workflow",
		"Active Workflow",
		"native submission",
		"ERPNext has posted",
		"No Warehouse",
		"Standard Sales Invoice completion is blocked",
	):
		assert forbidden not in text

	# Existing server-authoritative pricing, accounting, stock and workflow paths stay unchanged.
	for contract in (
		"get_standard_sales_invoice_completion_preview",
		"update_standard_sales_invoice_draft",
		"submit_standard_sales_invoice",
		"apply_standard_sales_invoice_workflow_action",
		"get_standard_sales_invoice_completion_item_pricing",
		"get_professional_selling_record_actions",
		"preview.return_outstanding_policy.mode === 'reduce_source_outstanding'",
		"preview.can_edit_update_stock",
		"canOverrideRate",
		"source_locked",
		"expected_modified",
		"expected_workflow_state",
		"confirmAboveEdgeModal",
		"window.retailedge?.userErrorMessage?.(error, fallback)",
	):
		assert contract in text

	# The browser must not manufacture accounting or workflow state locally.
	for forbidden in (
		".workflow_state =",
		".docstatus =",
		".outstanding_amount =",
	):
		assert forbidden not in text

	# Keep Vue methods outside the watch block; this catches accidental brace loss in full-file edits.
	assert "\t\t},\n\t},\n\tmethods: {" in text
