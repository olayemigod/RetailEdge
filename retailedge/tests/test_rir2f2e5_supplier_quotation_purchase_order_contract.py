from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_supplier_quotation_purchase_order.py"
BUNDLE = ROOT / "public" / "js" / "professional_purchasing.bundle.js"
HISTORY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalSupplierQuotationHistoryOverlay.vue"
OVERLAY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalSupplierQuotationPurchaseOrderOverlay.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str, next_name: str | None = None) -> str:
	start = source.index(f"def {name}(")
	if next_name:
		end = source.index(f"def {next_name}(", start + 1)
		return source[start:end]
	return source[start:]


def test_preview_uses_erpnext_supplier_quotation_mapper_without_persisting():
	source = _read(BACKEND)
	preview = _function_source(
		source,
		"get_supplier_quotation_purchase_order_preview",
		"create_purchase_order_draft_from_supplier_quotation",
	)
	assert "from erpnext.buying.doctype.supplier_quotation.supplier_quotation import make_purchase_order" in source
	assert "make_purchase_order(doc.name)" in source
	assert '"persistence": "none"' in preview
	assert "purchase_order.insert(" not in preview
	assert "purchase_order.submit(" not in preview
	assert "frappe.db.commit" not in preview


def test_conversion_requires_submitted_readable_quote_and_single_safe_branch():
	source = _read(BACKEND)
	assert "_assert_read(SUPPLIER_QUOTATION_DOCTYPE, name)" in source
	assert "Only submitted Supplier Quotations can prepare a Purchase Order" in source
	assert 'BLOCKED_SUPPLIER_QUOTATION_STATUSES = {"Cancelled", "Stopped", "Expired"}' in source
	assert "validate_user_branch_access(" in source
	assert "spans multiple Branches and requires Advanced ERPNext review" in source
	assert "is not attributable to a permitted Branch" in source
	assert "Supplier Quotation Branch does not match its linked Request for Quotation Branch" in source


def test_draft_creation_is_post_only_locked_stale_safe_duplicate_safe_and_never_submits():
	source = _read(BACKEND)
	create = _function_source(source, "create_purchase_order_draft_from_supplier_quotation")
	assert '@frappe.whitelist(methods=["POST"])' in source
	assert "FOR UPDATE" in create
	assert "expected_supplier_quotation_modified" in create
	assert "changed after the preview" in create
	assert "_existing_active_purchase_order(doc.name)" in create
	assert "already references Supplier Quotation" in create
	assert "purchase_order.insert()" in create
	assert "purchase_order.submit(" not in create
	assert "ignore_permissions=True" not in create
	assert "frappe.db.commit" not in create
	assert 'frappe.new_doc("GL Entry")' not in source
	assert 'frappe.new_doc("Stock Ledger Entry")' not in source
	assert '"posting_status": "Draft"' in create


def test_duplicate_detection_does_not_expose_existing_purchase_order_identity():
	source = _read(BACKEND)
	assert "def _existing_active_purchase_order(supplier_quotation: str) -> bool:" in source
	assert "return bool(rows)" in source
	assert '"existing_purchase_order": existing' in source
	assert "Purchase Order {0} already references" not in source


def test_supplier_quotation_history_exposes_edgesuite_prepare_po_only_for_eligible_rows():
	history = _read(HISTORY)
	assert "Prepare PO" in history
	assert 'const PREPARE_PO_EVENT = "retailedge-open-supplier-quotation-purchase-order"' in history
	assert "canPreparePurchaseOrder(row)" in history
	assert 'Number(row?.docstatus || 0) === 1' in history
	assert '["Cancelled", "Stopped", "Expired"].includes(status)' in history
	assert "new CustomEvent(PREPARE_PO_EVENT" in history
	assert 'const REFRESH_EVENT = "retailedge-refresh-professional-supplier-quotation-history"' in history


def test_conversion_overlay_stays_inside_edgesuite_and_creates_only_draft():
	overlay = _read(OVERLAY)
	assert "get_supplier_quotation_purchase_order_preview" in overlay
	assert "create_purchase_order_draft_from_supplier_quotation" in overlay
	assert "Create Draft Purchase Order" in overlay
	assert '}, "POST")' in overlay
	assert "Purchase Order submission is not performed by this action" in overlay
	assert "frappe.set_route" not in overlay
	assert "frappe.new_doc" not in overlay
	assert 'window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"))' in overlay


def test_professional_purchasing_bundle_mounts_conversion_overlay():
	bundle = _read(BUNDLE)
	assert 'import ProfessionalSupplierQuotationPurchaseOrderOverlay from "./professional_purchasing/ProfessionalSupplierQuotationPurchaseOrderOverlay.vue"' in bundle
	assert 'supplierQuotationPurchaseOrderRoot.className = "retailedge-supplier-quotation-purchase-order-overlay-root"' in bundle
	assert "edgeUI.createEdgeApp(ProfessionalSupplierQuotationPurchaseOrderOverlay)" in bundle
	assert "supplierQuotationPurchaseOrderApp.unmount?.()" in bundle
