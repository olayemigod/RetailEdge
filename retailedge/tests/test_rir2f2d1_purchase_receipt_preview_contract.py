from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_purchase_receipt.py"
CONTROLLER = ROOT / "retailedge" / "page" / "professional_purchasing" / "professional_purchasing.js"
OVERLAY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchaseReceiptPreviewOverlay.vue"
BUNDLE = ROOT / "public" / "js" / "professional_purchase_receipt_preview.bundle.js"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _preview_function(source: str) -> str:
	return source.split("def get_professional_purchase_receipt_preview", 1)[1].split("def submit_standard_purchase_receipt", 1)[0]


def test_preview_uses_erpnext_mapper_without_persisting_or_posting():
	source = _read(BACKEND)
	preview = _preview_function(source)
	assert "_map_receipt(po, branch)" in preview
	assert '"persistence": "none"' in preview
	assert '"posting_status": "Preview only"' in preview
	assert "receipt.insert(" not in preview
	assert "receipt.save(" not in preview
	assert "receipt.submit(" not in preview
	assert ".db_set(" not in preview


def test_preview_fails_into_advanced_handling_for_stock_control_complexity():
	source = _read(BACKEND)
	for contract in (
		"has_serial_no",
		"has_batch_no",
		"inspection_required_before_purchase",
		"rejected_quantity",
		"subcontracting",
	):
		assert contract in source
	assert '"standard_receipt_eligible": not blockers' in source


def test_professional_purchasing_routes_prepare_receipt_to_edgesuite_preview():
	source = _read(CONTROLLER)
	assert 'const REVIEW_RECEIPT_TRIGGER_LABEL = "Review Receipt"' in source
	assert "OPEN_PURCHASE_RECEIPT_PREVIEW_EVENT" in source
	assert 'data-retailedge-receipt-preview' in source
	assert "purchaseOrderFromRow(button)" in source
	assert "PREPARE_RECEIPT_TRIGGER_LABEL" not in source.split("hiddenButtonLabels:", 1)[1].split("],", 1)[0]


def test_capture_phase_intercepts_raw_and_rewritten_receipt_labels_before_vue_handler():
	source = _read(CONTROLLER)
	assert "[PREPARE_RECEIPT_TRIGGER_LABEL, REVIEW_RECEIPT_TRIGGER_LABEL].includes(label)" in source
	assert "event.preventDefault()" in source
	assert "event.stopPropagation()" in source
	assert "event.stopImmediatePropagation()" in source
	assert "OPEN_PURCHASE_RECEIPT_PREVIEW_EVENT" in source


def test_native_receipt_list_and_draft_handoff_remain_advanced_only():
	source = _read(CONTROLLER)
	assert 'const ADVANCED_PURCHASE_RECEIPTS_LABEL = "Advanced: Purchase Receipts in ERPNext"' in source
	assert "if (!nativeDeskEnabled()) return;" in source
	assert "PREPARE_RECEIPT_METHOD" in source
	assert 'frappe.set_route("Form", "Purchase Receipt", result.name)' in source


def test_preview_overlay_remains_edgesuite_owned_after_d2():
	overlay = _read(OVERLAY)
	bundle = _read(BUNDLE)
	controller = _read(CONTROLLER)
	assert "EdgeModal" in overlay
	assert "get_professional_purchase_receipt_preview" in overlay
	assert "mountRetailEdgeProfessionalPurchaseReceiptPreview" in bundle
	assert "PURCHASE_RECEIPT_PREVIEW_ASSET" in controller
	assert "mountRetailEdgeProfessionalPurchaseReceiptPreview" in controller
