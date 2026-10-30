from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
MAKE_SALE = APP_ROOT / "public" / "js" / "make_sale" / "MakeSale.vue"
REVIEW = APP_ROOT / "public" / "js" / "make_sale" / "SalesInvoiceSubmissionReview.vue"
UNFINISHED = APP_ROOT / "public" / "js" / "make_sale" / "UnfinishedSalesPanel.vue"
WORKBENCH = APP_ROOT / "sales_invoice_workbench.py"
BASELINE_PATCH = APP_ROOT / "patches" / "ensure_retailedge_cashier_operational_permissions.py"
OUTPUT_PATCH = APP_ROOT / "patches" / "ensure_retailedge_cashier_sales_output_access.py"
PATCHES = APP_ROOT / "patches.txt"
OUTPUT_PAGE = APP_ROOT / "retailedge" / "page" / "document_output_sharing" / "document_output_sharing.json"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_make_sale_requires_complete_review_before_direct_submit():
	make_sale = _read(MAKE_SALE)
	review = _read(REVIEW)
	workbench = _read(WORKBENCH)

	assert 'PREVIEW_METHOD = "retailedge.sales_invoice_workbench.get_sales_invoice_submission_review"' in make_sale
	assert "<SalesInvoiceSubmissionReview" in make_sale
	assert 'v-if="savedDocument.review_complete"' in make_sale
	assert "confirmSavedDocumentSubmission" in make_sale
	assert "Submit Reviewed Sale" in make_sale
	assert "!savedDocument.review_complete" in make_sale
	assert '"review_complete": True' in workbench
	assert "get_standard_sales_invoice_completion_preview" in workbench
	assert 'for row in list(doc.get("items") or [])' in workbench
	assert "[:MAX_ITEM_SUMMARY]" not in workbench

	for label in (
		"Review before submission",
		"Customer",
		"Posting date",
		"Stock posting",
		"Item",
		"Qty",
		"Rate",
		"Amount",
		"Subtotal",
		"Taxes & charges",
		"Total",
		"Amount due",
	):
		assert label in review


def test_make_sale_can_resume_server_saved_drafts_after_browser_session_loss():
	make_sale = _read(MAKE_SALE)
	unfinished = _read(UNFINISHED)
	workbench = _read(WORKBENCH)

	assert 'DRAFTS_METHOD = "retailedge.sales_invoice_workbench.get_resumable_sales_invoice_drafts"' in make_sale
	assert "<UnfinishedSalesPanel" in make_sale
	assert "refreshUnfinishedSales" in make_sale
	assert "resumeUnfinishedSale" in make_sale
	assert "reviewUnfinishedSale" in make_sale
	assert "Continue a saved sale" in unfinished
	assert "Resume Sale" in unfinished
	assert '"owner": user' in workbench
	assert '"docstatus": 0' in workbench
	assert '"is_pos": 0' in workbench
	assert "get_operating_context" in workbench
	assert 'frappe.has_permission(SALES_INVOICE_DOCTYPE, "write", doc=doc)' in workbench
	assert "get_standard_sales_invoice_completion_preview(row.name" in workbench


def test_cashier_receipt_print_and_document_output_use_native_permissions():
	baseline = _read(BASELINE_PATCH)
	output_patch = _read(OUTPUT_PATCH)
	patches = _read(PATCHES)
	page = _read(OUTPUT_PAGE)

	assert '"print"' in baseline
	assert 'update_permission_property("Sales Invoice", role, PERMLEVEL, "print", 1)' in output_patch
	assert 'OUTPUT_PAGE = "document-output-sharing"' in output_patch
	assert 'page.append("roles", {"role": role})' in output_patch
	assert "retailedge.patches.ensure_retailedge_cashier_sales_output_access" in patches
	assert '"role": "RetailEdge Cashier"' in page
	assert '"role": "RetailEdgeCashier"' in page
