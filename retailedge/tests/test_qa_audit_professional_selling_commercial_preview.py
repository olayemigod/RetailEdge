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
