from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_supplier_quotation_capture.py"
OVERLAY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalRfqHistoryOverlay.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str, next_name: str | None = None) -> str:
	start = source.index(f"def {name}(")
	if next_name:
		end = source.index(f"def {next_name}(", start + 1)
		return source[start:end]
	return source[start:]


def _vue_method_source(source: str, start_marker: str, end_marker: str) -> str:
	start = source.index(start_marker)
	end = source.index(end_marker, start + len(start_marker))
	return source[start:end]


def test_capture_preview_is_read_only_and_erpnext_mapped():
	source = _read(BACKEND)
	preview = _function_source(source, "get_supplier_quotation_capture_preview", "record_submitted_supplier_quotation_from_rfq")
	assert "make_supplier_quotation_from_rfq" in source
	assert '"persistence": "none"' in preview
	assert '"source_of_truth": "ERPNext RFQ to Supplier Quotation mapper"' in preview
	assert '"can_record": bool(selected_supplier and items and not blockers)' in preview
	assert "mapped.insert(" not in preview
	assert "mapped.submit(" not in preview
	assert "frappe.db.commit" not in preview


def test_capture_is_standard_rfq_response_only_and_blocks_governed_cases():
	source = _read(BACKEND)
	assert '"Workflow"' in source
	assert '"document_type": SUPPLIER_QUOTATION_DOCTYPE' in source
	assert '"is_active": 1' in source
	assert "approval Workflow" in source
	assert '_permission(SUPPLIER_QUOTATION_DOCTYPE, "create")' in source
	assert '_permission(SUPPLIER_QUOTATION_DOCTYPE, "submit")' in source
	assert "is not part of Request for Quotation" in source
	assert "Subcontracted Supplier Quotations remain an Advanced ERPNext workflow" in source
	assert "A Supplier Quotation already exists for this Supplier and RFQ" in source
	assert "request_for_quotation = %s" in source


def test_restricted_blank_branch_rfq_fails_closed():
	source = _read(BACKEND)
	assert "_document_branch(doc)" in source
	assert "user_has_global_branch_access(user=frappe.session.user)" in source
	assert "validate_user_branch_access(" in source
	assert "has no Branch attribution for your restricted access" in source


def test_item_rates_are_exactly_bound_to_mapped_rfq_items():
	source = _read(BACKEND)
	assert 'row.get("request_for_quotation_item")' in source
	assert "Quoted rates cannot be negative" in source
	assert "RFQ item {0} was supplied more than once" in source
	assert "set(rates) != expected" in source
	assert "Enter one quoted rate for every RFQ item and do not add unrelated items" in source
	assert "row.rate = rates[str(row.request_for_quotation_item)]" in source


def test_record_submit_is_post_only_locked_stale_safe_and_erpnext_authoritative():
	source = _read(BACKEND)
	record = _function_source(source, "record_submitted_supplier_quotation_from_rfq")
	assert '@frappe.whitelist(methods=["POST"])' in source
	assert "FOR UPDATE" in record
	assert "expected_rfq_modified" in record
	assert "changed after your review" in record
	assert "_standard_blockers(rfq, supplier)" in record
	assert "_mapped_supplier_quotation(rfq, supplier)" in record
	assert "mapped.insert()" in record
	assert "mapped.submit()" in record
	assert "ignore_permissions=True" not in record
	assert "frappe.db.commit" not in record
	assert 'frappe.new_doc("GL Entry")' not in source
	assert 'frappe.new_doc("Stock Ledger Entry")' not in source
	assert '"source_of_truth": "ERPNext Supplier Quotation insert + submit"' in record


def test_rfq_history_exposes_submitted_rfq_quote_capture_without_native_desk():
	overlay = _read(OVERLAY)
	assert "Record Supplier Quote" in overlay
	assert "Number(row?.docstatus || 0) === 1" in overlay
	assert "get_supplier_quotation_capture_preview" in overlay
	assert "record_submitted_supplier_quotation_from_rfq" in overlay
	assert "Record & Submit Supplier Quotation" in overlay
	assert '}, "POST")' in overlay
	assert "capture.preview.suppliers" in overlay
	assert "request_for_quotation_item" in overlay
	assert "expected_rfq_modified" in overlay
	assert "ERPNext's RFQ → Supplier Quotation mapper" in overlay
	assert "Ad-hoc quotations" in overlay


def test_capture_submit_stays_inside_edgesuite_and_refreshes_quote_history():
	overlay = _read(OVERLAY)
	record = _vue_method_source(overlay, "async recordAndSubmitQuote()", "leaveCapture()")
	assert "CAPTURE_RECORD_METHOD" in record
	assert '"POST"' in record
	assert "frappe.set_route" not in record
	assert "frappe.new_doc" not in record
	assert 'window.dispatchEvent(new CustomEvent("retailedge-refresh-professional-supplier-quotation-history"))' in record


def test_existing_advanced_rfq_routes_are_preserved_as_deliberate_fallbacks():
	overlay = _read(OVERLAY)
	assert "nativeFallbackEnabled" in overlay
	assert "Advanced: Open in ERPNext" in overlay
	assert "Advanced: RFQs in ERPNext" in overlay
	assert 'frappe.set_route("Form", "Request for Quotation", name)' in overlay
	assert 'frappe.set_route("List", "Request for Quotation")' in overlay
