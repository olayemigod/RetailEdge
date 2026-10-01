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
	preview = _function_source(source, "get_purchase_order_submit_preview", "update_standard_purchase_order_draft")
	assert '"persistence": "none"' in preview
	assert '"blockers": blockers' in preview
	assert '"can_submit": not blockers' in preview
	assert "doc.submit(" not in preview
	assert "doc.save(" not in preview
	assert "frappe.db.commit" not in preview


def test_draft_purchase_order_edit_is_bounded_stale_safe_and_erpnext_validated():
	source = _read(BACKEND)
	overlay = _read(OVERLAY)
	update = _function_source(source, "update_standard_purchase_order_draft", "apply_standard_purchase_order_workflow_action")
	assert '@frappe.whitelist(methods=["POST"])' in source
	assert "FOR UPDATE" in update
	assert "expected_purchase_order_modified" in update
	assert "changed after it was opened" in update
	assert 'frappe.has_permission(PURCHASE_ORDER_DOCTYPE, "write", doc=doc)' in update
	assert "doc.transaction_date = transaction_date" in update
	assert "row.qty = qty" in update
	assert "row.rate = rate" in update
	assert "row.schedule_date = row_schedule" in update
	assert "doc.save()" in update
	assert "Subcontracting Purchase Orders require Advanced ERPNext review." in update
	assert "Inter-company Purchase Orders require Advanced ERPNext review." in update
	assert "ignore_permissions=True" not in update
	assert "Company, Supplier, Branch, Stock Location, Buying Price List and existing item" in update
	assert "update_standard_purchase_order_draft" in overlay
	assert "Edit draft before completion" in overlay
	assert "Save Draft Changes" in overlay
	assert "draftDirty" in overlay
	assert "Discard unsaved Purchase Order changes?" in overlay
	assert "confirmAboveEdgeModal" in overlay


def test_draft_purchase_order_editor_can_add_new_items_safely():
	source = _read(BACKEND)
	overlay = _read(OVERLAY)
	update = _function_source(source, "update_standard_purchase_order_draft", "apply_standard_purchase_order_workflow_action")
	assert "search_purchase_order_draft_items" in source
	assert "get_purchase_order_draft_item_pricing" in source
	assert "resolve_purchase_item_pricing" in source
	assert "doc.append(\"items\", {\"item_code\": item_code})" in update
	assert "Existing Purchase Order item identity cannot be replaced here" in update
	assert "MAX_ITEMS" in update
	assert "set_missing_values" in update
	assert "Add Item" in overlay
	assert "searchDraftItem" in overlay
	assert "refreshDraftItemPricing" in overlay
	assert "item_code: row.item_code || \"\"" in overlay
	assert "v-if=\"!row.name\"" in overlay


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


def test_restricted_blank_or_disabled_branch_fails_closed_before_submission():
	source = _read(BACKEND)
	assert "_document_branch(doc)" in source
	assert "get_operational_branch_scope(company, user=frappe.session.user)" in source
	assert "validate_operating_branch(" in source
	assert '"allowed_branches"' in source
	assert "active operational access to Branch" in source
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
	assert 'getattr(doc, "docstatus", 0)' in submit
	assert "ignore_permissions=True" not in submit
	assert "frappe.db.commit" not in submit
	assert 'frappe.new_doc("GL Entry")' not in source
	assert 'frappe.new_doc("Stock Ledger Entry")' not in source
	assert '"source_of_truth": "ERPNext Purchase Order submit"' in submit



def test_submitted_purchase_order_exposes_permission_aware_receipt_and_invoice_actions():
	source = _read(BACKEND)
	overlay = _read(OVERLAY)
	for contract in (
		"def _submitted_next_actions",
		'_permission("Purchase Receipt", "create")',
		'_permission("Purchase Invoice", "create")',
		'"value": "receive-stock"',
		'"value": "create-purchase-invoice"',
		'"next_actions": _submitted_next_actions(doc)',
		'"next_actions": _submitted_next_actions(current)',
	):
		assert contract in source
	assert '"docstatus": cint(getattr(doc, "docstatus", 0))' in source
	assert '"per_received": flt(getattr(doc, "per_received", 0))' in source
	assert '"per_billed": flt(getattr(doc, "per_billed", 0))' in source

	for contract in (
		"submittedNextActions",
		"runSubmittedNextAction(action.value)",
		"retailedge-open-professional-purchase-receipt-preview",
		"prepare_purchase_invoice_from_purchase_order",
		"retailedge-professional-purchasing-purchase-invoice-ready",
	):
		assert contract in overlay


def test_submit_overlay_requires_review_and_stays_inside_edgesuite():
	overlay = _read(OVERLAY)
	assert "Review & Submit Purchase Order" in overlay
	assert "get_purchase_order_submit_preview" in overlay
	assert "submit_standard_purchase_order" in overlay
	assert "preview?.can_submit && !preview?.workflow_eligible && !submitted" in overlay
	assert "Submit Purchase Order" in overlay
	assert '}, "POST")' in overlay
	assert "expected_purchase_order_modified" in overlay
	assert "Advanced: ERPNext" in overlay
	assert "nativeDeskAllowed" in overlay
	assert 'frappe.set_route("Form", "Purchase Order", this.purchaseOrder)' in overlay
	assert "frappe.new_doc" not in overlay
	assert "does not create a receipt, invoice, GL Entry or Stock Ledger Entry" in overlay
	assert 'window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"))' in overlay


def test_bundle_does_not_inject_a_duplicate_purchase_order_review_action():
	bundle = _read(BUNDLE)
	assert "ProfessionalPurchaseOrderSubmitOverlay" in bundle
	assert "removeLegacyPurchaseOrderSubmitButtons" in bundle
	assert 'target.querySelectorAll(\'[data-retailedge-po-submit="true"]\')' in bundle
	assert 'const PURCHASE_ORDER_SUBMIT_LABEL = "Review & Submit"' not in bundle
	assert 'button.setAttribute("data-retailedge-po-submit", "true")' not in bundle
	assert "purchaseOrderFromRow(button)" not in bundle


def test_bundle_mounts_and_cleans_up_po_submit_overlay():
	bundle = _read(BUNDLE)
	assert 'import ProfessionalPurchaseOrderSubmitOverlay from "./professional_purchasing/ProfessionalPurchaseOrderSubmitOverlay.vue"' in bundle
	assert 'purchaseOrderSubmitRoot.className = "retailedge-purchase-order-submit-overlay-root"' in bundle
	assert "edgeUI.createEdgeApp(ProfessionalPurchaseOrderSubmitOverlay)" in bundle
	assert "purchaseOrderSubmitApp.unmount?.()" in bundle
	assert "purchaseOrderSubmitRoot.remove()" in bundle
	assert "app._retailedgePurchaseOrderSubmitApp = purchaseOrderSubmitApp" in bundle
