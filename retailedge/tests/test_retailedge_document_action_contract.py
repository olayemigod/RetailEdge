from __future__ import annotations

import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_JS = APP_ROOT / "public" / "js"


def _sources():
	for path in sorted(PUBLIC_JS.rglob("*")):
		if path.suffix not in {".js", ".vue"}:
			continue
		yield path, path.read_text(encoding="utf-8")


def test_view_actions_never_use_document_output_sharing_as_their_preview_surface():
	for path, source in _sources():
		assert not re.search(
			r'retailedgeDocumentOutputTarget\s*=\s*\{[^}]{0,500}mode\s*:\s*["\']view["\']',
			source,
			flags=re.S,
		), f"{path}: View must not target Document Output & Sharing"
		assert not re.search(
			r'openDocumentOutput\([^\n)]*["\']view["\']',
			source,
		), f"{path}: operational View must use a review/preview surface"
		assert 'target.mode === "view"' not in source, f"{path}: Document Output must not retain legacy View mode"
		assert "outputMode === 'view'" not in source
		assert 'outputMode === "view"' not in source
		assert "outputMode !== 'view'" not in source
		assert 'outputMode !== "view"' not in source


def test_print_share_has_one_global_route_contract():
	runtime = (PUBLIC_JS / "retailedge.js").read_text(encoding="utf-8")
	output = (PUBLIC_JS / "document_output_sharing" / "DocumentOutputSharing.vue").read_text(encoding="utf-8")
	assert "openDocumentOutputSharing = function" in runtime
	assert 'mode: "share"' in runtime
	assert 'frappe.set_route("document-output-sharing")' in runtime
	assert "outputMode" not in output
	assert 'class="edge-panel output-actions"' in output


def test_document_output_target_assignment_is_centralised():
	for path, source in _sources():
		if path == PUBLIC_JS / "retailedge.js":
			continue
		assert "retailedgeDocumentOutputTarget =" not in source, (
			f"{path}: use window.retailedge.openDocumentOutputSharing(...) instead of assigning the output target directly"
		)
		assert 'frappe.set_route("document-output-sharing")' not in source, (
			f"{path}: Print & Share routing must go through the shared RetailEdge helper"
		)


def test_core_transaction_lists_keep_view_review_and_output_meanings_separate():
	selling = (PUBLIC_JS / "professional_selling" / "ProfessionalSelling.vue").read_text(encoding="utf-8")
	purchasing = (PUBLIC_JS / "professional_purchasing" / "ProfessionalPurchasing.vue").read_text(encoding="utf-8")
	purchase_order_review = (PUBLIC_JS / "professional_purchasing" / "ProfessionalPurchaseOrderSubmitOverlay.vue").read_text(encoding="utf-8")
	purchase_receipt_history = (PUBLIC_JS / "professional_purchasing" / "ProfessionalPurchaseReceiptHistoryOverlay.vue").read_text(encoding="utf-8")
	purchase_receipt_review = (PUBLIC_JS / "professional_purchasing" / "ProfessionalPurchaseReceiptPreviewOverlay.vue").read_text(encoding="utf-8")
	payments = (PUBLIC_JS / "payment_management" / "PaymentHistoryPanel.vue").read_text(encoding="utf-8")
	make_sale = (PUBLIC_JS / "make_sale" / "MakeSale.vue").read_text(encoding="utf-8")

	assert 'if (action === "view") { this.openRecordPreview(document, row); return; }' in selling
	assert 'if (action === "output") { this.openDocumentOutput(document, row); return; }' in selling
	assert "openDocumentOutputSharing" in selling
	assert 'Number(row.docstatus || 0) === 0 ? "Review / Edit" : "View"' in purchasing
	assert `openDocumentOutput('purchase-order', row.name)` in purchasing
	assert '"purchase-order", this.submitted.name' in purchase_order_review
	assert "Print & Share" in purchase_order_review
	assert `openDocumentOutput(row.name)` in purchase_receipt_history
	assert '"purchase-receipt", name' in purchase_receipt_history
	assert '"purchase-receipt", this.submitted.name' in purchase_receipt_review
	assert "Print & Share" in purchase_receipt_review
	assert 'Number(row.docstatus || 0) === 0 ? "Review" : "View"' in payments
	assert 'this.deliveryCompletionOpen = true;' in make_sale
	assert 'openDocumentOutput("delivery-note", result.name, "view")' not in make_sale
