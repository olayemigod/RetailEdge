from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_purchase_receipt.py"
CONTROLLER = ROOT / "retailedge" / "page" / "professional_purchasing" / "professional_purchasing.js"
OVERLAY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchaseReceiptPreviewOverlay.vue"
BUNDLE = ROOT / "public" / "js" / "professional_purchase_receipt_preview.bundle.js"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_preview_uses_erpnext_mapper_without_persisting_or_posting():
	source = _read(BACKEND)
	assert "make_purchase_receipt(po.name)" in source
	assert '"persistence": "none"' in source
	assert '"posting_status": "Preview only"' in source
	assert "receipt.insert(" not in source
	assert "receipt.save(" not in source
	assert "receipt.submit(" not in source
	assert ".db_set(" not in source


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


def test_native_receipt_list_and_draft_handoff_remain_advanced_only():
	source = _read(CONTROLLER)
	assert 'const ADVANCED_PURCHASE_RECEIPTS_LABEL = "Advanced: Purchase Receipts in ERPNext"' in source
	assert "if (!nativeDeskEnabled()) return;" in source
	assert "PREPARE_RECEIPT_METHOD" in source
	assert 'frappe.set_route("Form", "Purchase Receipt", result.name)' in source


def test_preview_overlay_is_edgesuite_mounted_and_has_no_post_action():
	overlay = _read(OVERLAY)
	bundle = _read(BUNDLE)
	controller = _read(CONTROLLER)
	assert "EdgeModal" in overlay
	assert "get_professional_purchase_receipt_preview" in overlay
	assert "No document has been created and no stock has moved" in overlay
	assert "submit" not in overlay.lower()
	assert "mountRetailEdgeProfessionalPurchaseReceiptPreview" in bundle
	assert "PURCHASE_RECEIPT_PREVIEW_ASSET" in controller
	assert "mountRetailEdgeProfessionalPurchaseReceiptPreview" in controller
