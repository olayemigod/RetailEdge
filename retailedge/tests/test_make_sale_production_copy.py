from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "public/js/make_sale/MakeSale.vue"


def test_make_sale_uses_business_facing_copy_and_preserves_completion_authority():
	text = PAGE.read_text(encoding="utf-8")

	for contract in (
		"Sales Invoice submitted. Continue with the next valid customer workflow or start another sale.",
		"The Sales Invoice draft is saved. You can complete it or start another sale.",
		"Approval and submission stay on this page. Quick Sale saves the draft for review first.",
		"Approval workflow",
		"Standard submission",
		"Only actions currently permitted by the approval workflow are shown.",
		"Submit uses standard Sales Invoice validation, accounting and stock posting rules.",
		"Advanced: Open Sales Invoice",
		"This browser session keeps a temporary recovery copy until the draft is saved.",
		"Complete the required fields, then save the draft.",
		"Leave Make Sale? Unsaved changes are kept temporarily in this browser session, but no draft has been saved yet.",
		"Open the saved Sales Invoice in the advanced form? Unsaved page edits are not carried until you update the draft.",
		"Open the advanced Sales Invoice form? Save this Make Sale draft first if you want the current page entries recorded.",
		'erpnext_default: "System default"',
		'}[source] || "Standard pricing"',
	):
		assert contract in text

	for forbidden in (
		"ERPNext has submitted the Sales Invoice",
		"The ERPNext Sales Invoice draft",
		"Quick Sale only creates the ERPNext draft",
		"Frappe Workflow",
		"ERPNext submission",
		"Only actions currently permitted by Frappe Workflow",
		"Submit uses ERPNext's normal Sales Invoice validation",
		"Advanced: ERPNext",
		"until the ERPNext draft is saved",
		"save the ERPNext draft",
		"no ERPNext draft has been created yet",
		"Advanced ERPNext?",
		"advanced ERPNext Sales Invoice form",
		"recorded in ERPNext",
		'erpnext_default: "ERPNext default"',
		'}[source] || "ERPNext pricing"',
	):
		assert forbidden not in text

	# Preserve the server-authoritative draft, submit and workflow paths.
	for contract in (
		"retailedge.guided_sales_invoice.create_simple_sales_invoice_draft",
		"retailedge.standard_sales_invoice_completion.update_standard_sales_invoice_draft",
		"retailedge.standard_sales_invoice_completion.get_standard_sales_invoice_completion_preview",
		"retailedge.standard_sales_invoice_completion.submit_standard_sales_invoice",
		"retailedge.standard_sales_invoice_completion.apply_standard_sales_invoice_workflow_action",
		"canUseNativeDesk",
		"openAdvancedNative",
	):
		assert contract in text

	for forbidden in (
		".docstatus =",
		".workflow_state =",
	):
		assert forbidden not in text
