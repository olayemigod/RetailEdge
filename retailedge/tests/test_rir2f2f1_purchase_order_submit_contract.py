from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_purchase_order_submit.py"
BUNDLE = ROOT / "public" / "js" / "professional_purchasing.bundle.js"
OVERLAY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchaseOrderSubmitOverlay.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str, next_name: str | None = None) -> str:
	start = source.index(f"def {name}(")
	if next_name:
		end = source.index(f"def {next_name}(", start + 1)
		return source[start:end]
	return source[start:]


def test_submit_preview_is_read_only_and_exposes_blockers():
	source = _read(BACKEND)
	preview = _function_source(source, "get_purchase_order_submit_preview", "submit_standard_purchase_order")
	assert '"persistence": "none"' in preview
	assert '"blockers": blockers' in preview
	assert '"can_submit": not blockers' in preview
	assert "doc.submit(" not in preview
	assert "doc.save(" not in preview
	assert "frappe.db.commit" not in preview


def test_standard_submit_blocks_workflows_and_advanced_po_cases():
	source = _read(BACKEND)
	assert 'frappe.db.get_value(' in source
	assert '"Workflow"' in source
	assert '"document_type": PURCHASE_ORDER_DOCTYPE' in source
	assert '"is_active": 1' in source
	assert "approval Workflow" in source
	assert "is_subcontracted" in source
	assert "is_old_subcontracting_flow" in source
	assert "is_internal_supplier" in source
	assert "inter_company_order_reference" in source
	assert 'BLOCKED_DRAFT_STATUSES = {"On Hold", "Closed", "Cancelled"}' in source
	assert '_permission(PURCHASE_ORDER_DOCTYPE, "submit", doc.name)' in source


def test_restricted_blank_branch_fails_closed_before_submission():
	source = _read(BACKEND)
	assert "_document_branch(doc)" in source
	assert "user_has_global_branch_access(user=frappe.session.user)" in source
	assert "validate_user_branch_access(" in source
	assert "has no Branch attribution for your restricted access" in source


def test_submit_is_post_only_locked_stale_safe_and_erpnext_authoritative():
	source = _read(BACKEND)
	submit = _function_source(source, "submit_standard_purchase_order")
	assert '@frappe.whitelist(methods=["POST"])' in source
	assert "FOR UPDATE" in submit
	assert "expected_purchase_order_modified" in submit
	assert "changed after the review" in submit
	assert "_standard_submit_blockers(doc)" in submit
	assert "doc.submit()" in submit
	assert "doc.docstatus" in submit
	assert "ignore_permissions=True" not in submit
	assert "frappe.db.commit" not in submit
	assert 'frappe.new_doc("GL Entry")' not in source
	assert 'frappe.new_doc("Stock Ledger Entry")' not in source
	assert '"source_of_truth": "ERPNext Purchase Order submit"' in submit


def test_submit_overlay_requires_review_and_stays_inside_edgesuite():
	overlay = _read(OVERLAY)
	assert "Review & Submit Purchase Order" in overlay
	assert "get_purchase_order_submit_preview" in overlay
	assert "submit_standard_purchase_order" in overlay
	assert "preview?.can_submit && !submitted" in overlay
	assert "Submit Purchase Order" in overlay
	assert '}, "POST")' in overlay
	assert "expected_purchase_order_modified" in overlay
	assert "frappe.set_route" not in overlay
	assert "frappe.new_doc" not in overlay
	assert "does not create a receipt, invoice, GL Entry or Stock Ledger Entry" in overlay
	assert 'window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"))' in overlay


def test_bundle_adds_review_submit_only_to_draft_po_rows_and_capture_intercepts_it():
	bundle = _read(BUNDLE)
	assert 'const PURCHASE_ORDER_SUBMIT_LABEL = "Review & Submit"' in bundle
	assert 'const OPEN_PURCHASE_ORDER_SUBMIT_EVENT = "retailedge-open-purchase-order-submit"' in bundle
	assert 'target.querySelectorAll(".purchasing-table--orders tbody tr")' in bundle
	assert 'const status = normaliseButtonLabel(row.querySelector(".status-pill"))' in bundle
	assert 'if (status !== "Draft")' in bundle
	assert 'existing?.remove()' in bundle
	assert 'button.setAttribute("data-retailedge-po-submit", "true")' in bundle
	assert "purchaseOrderFromRow(button)" in bundle
	assert "event.preventDefault()" in bundle
	assert "event.stopImmediatePropagation()" in bundle
	assert "OPEN_PURCHASE_ORDER_SUBMIT_EVENT" in bundle


def test_bundle_mounts_and_cleans_up_po_submit_overlay():
	bundle = _read(BUNDLE)
	assert 'import ProfessionalPurchaseOrderSubmitOverlay from "./professional_purchasing/ProfessionalPurchaseOrderSubmitOverlay.vue"' in bundle
	assert 'purchaseOrderSubmitRoot.className = "retailedge-purchase-order-submit-overlay-root"' in bundle
	assert "edgeUI.createEdgeApp(ProfessionalPurchaseOrderSubmitOverlay)" in bundle
	assert "purchaseOrderSubmitApp.unmount?.()" in bundle
	assert "purchaseOrderSubmitRoot.remove()" in bundle
	assert "app._retailedgePurchaseOrderSubmitApp = purchaseOrderSubmitApp" in bundle
