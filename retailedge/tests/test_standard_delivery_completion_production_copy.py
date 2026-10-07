from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "public/js/professional_selling/StandardDeliveryCompletionDialog.vue"


def test_delivery_completion_uses_business_facing_copy_and_preserves_stock_authority():
	text = DIALOG.read_text(encoding="utf-8")

	# The completion surface should explain the business effect without platform internals.
	assert "Review the saved Delivery Note and submit it, or continue through the active approval workflow." in text
	assert "Review the saved Delivery Note and continue with any permitted next step." in text
	assert "Submitting this Delivery Note updates stock through the normal stock controls." in text
	assert "This review screen does not post stock independently." in text
	assert "Completion needs attention" in text
	assert "Approval workflow" in text
	assert "Active approval workflow" in text
	assert "ERPNext" not in text
	assert "Frappe Workflow" not in text
	assert "native stock submission" not in text
	assert "Stock Ledger" not in text

	# Stock and workflow effects remain delegated to the existing server-authoritative paths.
	for contract in (
		"get_standard_delivery_completion_preview",
		"update_standard_delivery_draft",
		"submit_standard_delivery_note",
		"apply_standard_delivery_workflow_action",
		"workflow_readiness?.available_actions",
		"expected_modified",
		"expected_workflow_state",
		"get_professional_selling_record_actions",
		"completedResult.next_actions",
		"window.retailedge?.userErrorMessage?.(error, fallback)",
	):
		assert contract in text

	for forbidden in (
		".workflow_state =",
		".docstatus =",
		".status =",
	):
		assert forbidden not in text
