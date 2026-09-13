from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_sourcing.py"
OVERLAY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalRfqPreviewOverlay.vue"
BUNDLE = ROOT / "public" / "js" / "professional_purchasing.bundle.js"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str, next_name: str | None = None) -> str:
	start = source.index(f"def {name}(")
	if next_name:
		end = source.index(f"def {next_name}(", start + 1)
		return source[start:end]
	return source[start:]


def test_standard_rfq_submit_is_post_only_and_rechecks_create_submit_permissions():
	source = _read(BACKEND)
	submit = _function_source(source, "submit_standard_request_for_quotation", "prepare_request_for_quotation_draft_advanced")
	assert '@frappe.whitelist(methods=["POST"])' in source
	assert "_assert_create(REQUEST_FOR_QUOTATION_DOCTYPE)" in submit
	assert "_assert_rfq_submit_permission()" in submit
	assert 'frappe.has_permission(REQUEST_FOR_QUOTATION_DOCTYPE, "submit")' in source
	assert "ignore_permissions=True" not in submit


def test_standard_rfq_submit_serializes_material_request_and_rejects_stale_preview():
	source = _read(BACKEND)
	submit = _function_source(source, "submit_standard_request_for_quotation", "prepare_request_for_quotation_draft_advanced")
	assert "SELECT name FROM `tabMaterial Request` WHERE name = %s FOR UPDATE" in submit
	assert "expected_material_request_modified" in submit
	assert "expected_modified != current_modified" in submit
	assert "changed after the RFQ preview" in submit
	assert "_validate_request_scope(request)" in submit


def test_duplicate_guard_uses_material_request_and_exact_supplier_set():
	source = _read(BACKEND)
	guard = _function_source(source, "_find_existing_active_rfq", "_docstatus_label")
	submit = _function_source(source, "submit_standard_request_for_quotation", "prepare_request_for_quotation_draft_advanced")
	assert '"Request for Quotation Item"' in guard
	assert 'filters={"material_request": material_request}' in guard
	assert '"docstatus": ["<", 2]' in guard
	assert '"Request for Quotation Supplier"' in guard
	assert "target_suppliers = set(supplier_names)" in guard
	assert "suppliers_by_parent.get(str(parent), set()) == target_suppliers" in guard
	assert "_find_existing_active_rfq(request.name, supplier_names)" in submit
	assert "already exists for this Material Request and Supplier set" in submit


def test_standard_submit_explicitly_disables_supplier_email_and_lets_erpnext_submit():
	source = _read(BACKEND)
	submit = _function_source(source, "submit_standard_request_for_quotation", "prepare_request_for_quotation_draft_advanced")
	assert 'rfq.append("suppliers", {"supplier": supplier, "send_email": 0})' in submit
	assert "rfq.insert()" in submit
	assert "rfq.submit()" in submit
	assert '"email_sending": False' in submit
	assert '"status": "Submitted"' in submit
	assert '"source_of_truth": "ERPNext Request for Quotation submit"' in submit
	assert "frappe.sendmail" not in submit
	assert "frappe.db.commit" not in submit


def test_preview_exposes_submit_permission_and_stale_guard_token():
	source = _read(BACKEND)
	preview = _function_source(source, "get_request_for_quotation_preview", "submit_standard_request_for_quotation")
	assert '"material_request_modified": str(getattr(request, "modified", None) or "")' in preview
	assert '"can_submit": bool(frappe.has_permission(REQUEST_FOR_QUOTATION_DOCTYPE, "submit"))' in preview
	assert '"persistence": "none"' in preview
	assert '"email_sending": False' in preview
	assert "rfq.insert(" not in preview
	assert "rfq.submit(" not in preview


def test_edgesuite_overlay_submits_standard_rfq_without_native_route():
	overlay = _read(OVERLAY)
	assert 'const SUBMIT_METHOD = "retailedge.professional_sourcing.submit_standard_request_for_quotation"' in overlay
	assert 'type: "POST"' in overlay
	assert "Create & Submit RFQ" in overlay
	assert "expected_material_request_modified: this.preview.material_request_modified" in overlay
	assert "this.suppliers.map((supplier) => supplier.value)" in overlay
	assert "this.submitted = await postMethod(SUBMIT_METHOD" in overlay
	assert "No supplier email was sent" in overlay
	assert "Supplier email remains off for every selected supplier" in overlay
	assert "frappe.set_route" not in overlay


def test_standard_success_stays_in_edgesuite_and_advanced_fallback_remains_separate():
	overlay = _read(OVERLAY)
	bundle = _read(BUNDLE)
	assert "Request for Quotation {{ submitted.name }} submitted in ERPNext" in overlay
	assert "Use RFQ History to review the submitted document" in overlay
	assert "Advanced: Prepare Draft in ERPNext" in overlay
	assert "nativeFallbackEnabled" in overlay
	assert 'const PREPARE_RFQ_METHOD = "retailedge.professional_sourcing.prepare_request_for_quotation_draft_advanced"' in bundle
	assert "if (!nativeDeskEnabled()) return;" in bundle
