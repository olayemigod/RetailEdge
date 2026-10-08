from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAKE_SALE = ROOT / "public/js/make_sale/MakeSale.vue"


def test_make_sale_uses_business_facing_copy_and_preserves_completion_authority():
	text = MAKE_SALE.read_text(encoding="utf-8")

	for contract in (
		"The Sales Invoice has been submitted.",
		"The Sales Invoice draft now owns the saved work.",
		"Quick Sale only creates the Sales Invoice draft.",
		"Approval Workflow",
		"Submission controls",
		"active approval workflow",
		"normal Sales Invoice validation, accounting and stock posting rules",
		"Advanced: Open Sales Invoice",
		"temporary recovery copy until the Sales Invoice draft is saved",
		"Default Selling Price List",
		"Standard pricing",
	):
		assert contract in text

	for forbidden in (
		"ERPNext",
		"Frappe Workflow",
		"Advanced: ERPNext",
	):
		assert forbidden not in text

	for contract in (
		"get_standard_sales_invoice_completion_preview",
		"submit_standard_sales_invoice",
		"apply_standard_sales_invoice_workflow_action",
		'savedDocument.workflow_readiness?.source === "frappe"',
		'v-if="canUseNativeDesk"',
		'@click="openAdvancedNative"',
	):
		assert contract in text
