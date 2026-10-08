from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORD_PURCHASE = ROOT / "public/js/record_purchase/RecordPurchase.vue"


def test_record_purchase_uses_business_facing_copy_and_preserves_purchase_invoice_authority():
	text = RECORD_PURCHASE.read_text(encoding="utf-8")

	for contract in (
		"Choose the purchase path first.",
		"standard purchasing documents",
		"Submitting the Purchase Invoice records the received stock.",
		"The Purchase Invoice has been submitted.",
		"The Purchase Invoice draft now owns the transaction.",
		"Quick Purchase only creates the Purchase Invoice draft.",
		"Approval Workflow",
		"Submission controls",
		"active approval workflow",
		"normal Purchase Invoice validation, payable and stock posting rules",
		"Advanced: Open Purchase Invoice",
		"temporary browser-session recovery copy is retained until the Purchase Invoice draft is saved",
		"Default Buying Price List",
		"Standard pricing",
		"advanced Purchase Invoice form",
	):
		assert contract in text

	for forbidden in (
		"ERPNext",
		"Frappe Workflow",
		"Advanced: ERPNext",
	):
		assert forbidden not in text

	for contract in (
		"create_simple_purchase_invoice_draft",
		"update_standard_purchase_invoice_draft",
		"get_standard_purchase_invoice_completion_preview",
		"submit_standard_purchase_invoice",
		"apply_standard_purchase_invoice_workflow_action",
		'savedDocument.workflow_readiness?.source === "frappe"',
		'v-if="canUseNativeDesk"',
		'@click="openAdvancedNative"',
		'erpnext_default: "Default Buying Price List"',
		'v-if="!editingSavedDraft" class="edge-button" type="button" @click="choosePurchaseType">Change Purchase Type</button>',
	):
		assert contract in text
