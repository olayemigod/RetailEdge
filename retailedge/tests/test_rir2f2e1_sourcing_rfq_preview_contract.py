from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_sourcing.py"
BUNDLE = ROOT / "public" / "js" / "professional_purchasing.bundle.js"
OVERLAY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalRfqPreviewOverlay.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str, next_name: str | None = None) -> str:
	start = source.index(f"def {name}(")
	if next_name:
		end = source.index(f"def {next_name}(", start + 1)
		return source[start:end]
	return source[start:]


def test_rfq_preview_uses_erpnext_mapper_without_persisting():
	source = _read(BACKEND)
	preview = _function_source(source, "get_request_for_quotation_preview", "prepare_request_for_quotation_draft_advanced")
	assert "make_request_for_quotation(request.name)" in source
	assert '"persistence": "none"' in preview
	assert '"email_sending": False' in preview
	assert "rfq.insert(" not in preview
	assert "rfq.save(" not in preview
	assert "rfq.submit(" not in preview
	assert ".db_set(" not in preview


def test_named_material_request_scope_fails_closed_for_restricted_blank_branch():
	source = _read(BACKEND)
	assert "elif not global_access:" in source
	assert "has no Branch attribution for your restricted access" in source
	assert "validate_user_branch_access(" in source
	assert "allowed_branches" in source


def test_advanced_rfq_fallback_is_post_only_branch_safe_and_draft_only():
	source = _read(BACKEND)
	advanced = _function_source(source, "prepare_request_for_quotation_draft_advanced")
	assert '@frappe.whitelist(methods=["POST"])' in source
	assert "_validate_request_scope(request)" in advanced
	assert 'rfq.append("suppliers", {"supplier": supplier, "send_email": 0})' in advanced
	assert "rfq.insert()" in advanced
	assert "rfq.submit(" not in advanced
	assert "ignore_permissions=True" not in advanced
	assert '"email_sending": False' in advanced
	assert '"status": "Draft"' in advanced


def test_material_request_rows_are_edgesuite_references_not_disguised_native_links():
	source = _read(BUNDLE)
	assert 'reference.classList.remove("link-button")' in source
	assert 'reference.classList.add("retailedge-material-request-reference")' in source
	assert 'reference.setAttribute("aria-disabled", "true")' in source
	assert 'const ADVANCED_MATERIAL_REQUEST_LABEL = "Advanced: Open in ERPNext"' in source
	assert "if (!nativeDeskEnabled())" in source
	assert 'button.setAttribute("data-retailedge-advanced-native", "Material Request")' in source


def test_start_rfq_is_capture_intercepted_into_edgesuite_preview():
	source = _read(BUNDLE)
	assert 'const START_RFQ_LABEL = "Start RFQ"' in source
	assert 'const OPEN_RFQ_PREVIEW_EVENT = "retailedge-open-professional-rfq-preview"' in source
	assert "if (label === START_RFQ_LABEL)" in source
	assert "materialRequestFromRow(button)" in source
	assert "event.preventDefault()" in source
	assert "event.stopPropagation()" in source
	assert "event.stopImmediatePropagation()" in source
	assert "OPEN_RFQ_PREVIEW_EVENT" in source


def test_rfq_preview_overlay_selects_suppliers_without_creating_a_document():
	overlay = _read(OVERLAY)
	assert "EdgeModal" in overlay
	assert "EdgeLinkField" in overlay
	assert "get_request_for_quotation_preview" in overlay
	assert 'kind: "rfq_supplier"' in overlay
	assert "No RFQ draft has been saved and no supplier email has been sent" in overlay
	assert "Preview RFQ" in overlay
	assert "rfq.insert(" not in overlay
	assert "frappe.set_route" not in overlay


def test_native_rfq_draft_handoff_is_explicit_advanced_only():
	bundle = _read(BUNDLE)
	overlay = _read(OVERLAY)
	assert "Advanced: Prepare Draft in ERPNext" in overlay
	assert "nativeFallbackEnabled" in overlay
	assert 'const ACCESS_MODE = "edgesuite_only"' in overlay
	assert 'const PREPARE_RFQ_METHOD = "retailedge.professional_sourcing.prepare_request_for_quotation_draft_advanced"' in bundle
	assert "if (!nativeDeskEnabled()) return;" in bundle
	assert 'type: "POST"' in bundle
	assert 'frappe.set_route("Form", "Request for Quotation", result.name)' in bundle
