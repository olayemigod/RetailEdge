from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPLETION = ROOT / "public/js/professional_selling/StandardSalesInvoiceCompletionDialog.vue"


def test_professional_selling_uses_shared_sales_commercial_preview():
	source = COMPLETION.read_text(encoding="utf-8")

	assert 'retailedge.sales_commercial_preview.get_sales_invoice_commercial_preview' in source
	assert 'import SalesCommercialSummary from "../selling/SalesCommercialSummary.vue";' in source
	assert '<SalesCommercialSummary' in source
	assert ':preview="commercialPreview"' in source
	assert ':loading="commercialPreviewLoading"' in source
	assert ':error="commercialPreviewError"' in source


def test_professional_selling_keeps_completion_governance_separate_from_commercial_preview():
	source = COMPLETION.read_text(encoding="utf-8")

	assert 'retailedge.standard_sales_invoice_completion.get_standard_sales_invoice_completion_preview' in source
	assert 'retailedge.standard_sales_invoice_completion.submit_standard_sales_invoice' in source
	assert 'retailedge.standard_sales_invoice_completion.apply_standard_sales_invoice_workflow_action' in source
	assert 'document_name: this.document.name' in source
	assert 'values: this.commercialPreviewValues()' in source
	assert 'await this.loadCommercialPreview();' in source


def test_saved_draft_commercial_preview_rejects_stale_async_results_during_debounce():
	source = COMPLETION.read_text(encoding="utf-8")

	for contract in (
		'commercialPreviewAppliedSignature: ""',
		"commercialPreviewSignature()",
		"this.commercialPreviewToken += 1;",
		'this.commercialPreviewAppliedSignature = "";',
		"const signature = this.commercialPreviewSignature();",
		"const token = ++this.commercialPreviewToken;",
		"token !== this.commercialPreviewToken || signature !== this.commercialPreviewSignature()",
		"this.commercialPreviewAppliedSignature = signature;",
	):
		assert contract in source

	queue_start = source.index("\t\tqueueCommercialPreview()")
	queue_end = source.index("\n\t\tasync loadCommercialPreview()", queue_start)
	queue = source[queue_start:queue_end]
	assert queue.index("this.commercialPreviewToken += 1;") < queue.index("window.setTimeout")
	assert "this.commercialPreviewLoading = true;" in queue


def test_saved_draft_preview_is_invalidated_when_document_leaves_editable_draft_state():
	source = COMPLETION.read_text(encoding="utf-8")

	assert source.count("this.commercialPreviewAppliedSignature = \"\";") >= 5
	assert source.count("this.commercialPreviewLoading = false;") >= 5
	assert "beforeUnmount()" in source
