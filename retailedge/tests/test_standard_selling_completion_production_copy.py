from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "public/js/professional_selling/StandardSellingCompletionDialog.vue"


def test_standard_selling_completion_uses_business_facing_copy_and_preserves_authority():
	text = DIALOG.read_text(encoding="utf-8")

	# Normal users should see business/process language, not platform implementation wording.
	assert "Review the saved draft and submit it, or continue through the active approval workflow." in text
	assert "Review the saved document and continue with any permitted next step." in text
	assert "Completion needs attention" in text
	assert "Approval workflow" in text
	assert "Active approval workflow" in text
	assert "ERPNext" not in text
	assert "Frappe Workflow" not in text
	assert "native submission" not in text

	# Completion remains server-authoritative and permission-aware.
	for contract in (
		"get_standard_selling_completion_preview",
		"update_standard_selling_draft",
		"submit_standard_selling_document",
		"apply_standard_selling_workflow_action",
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
