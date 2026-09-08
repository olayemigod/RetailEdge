from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_sourcing.py"
BUNDLE = ROOT / "public" / "js" / "professional_purchasing.bundle.js"
OVERLAY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalRfqHistoryOverlay.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_rfq_history_is_permission_and_branch_scoped_with_bounded_results():
	source = _read(BACKEND)
	assert "def get_request_for_quotation_history(" in source
	assert "_assert_read(REQUEST_FOR_QUOTATION_DOCTYPE)" in source
	assert "_resolve_scope(" in source
	assert "_branch_scoped_filters(" in source
	assert "frappe.get_list(" in source
	assert "MAX_RFQ_HISTORY = 100" in source
	assert "max(1, min(cint(limit) or 50, MAX_RFQ_HISTORY))" in source


def test_supplier_filter_is_reconciled_back_through_permission_scoped_parent_rows():
	source = _read(BACKEND)
	assert '"Request for Quotation Supplier"' in source
	assert 'filters={"supplier": supplier}' in source
	assert 'filters["name"] = ["in", candidate_names or ["__no_matching_rfq__"]]' in source
	assert "rows = frappe.get_list(" in source
	assert '"suppliers": suppliers_by_parent.get(name, [])' in source


def test_rfq_history_enriches_only_already_scoped_parent_names():
	source = _read(BACKEND)
	assert 'parent_names = [str(row.get("name") or "") for row in rows if row.get("name")]' in source
	assert 'filters={"parent": ["in", parent_names]}' in source
	assert '"Request for Quotation Item"' in source
	assert '"item_count": items_by_parent.get(name, 0)' in source


def test_existing_rfq_button_is_promoted_to_edgesuite_history():
	source = _read(BUNDLE)
	assert 'const RFQS_LABEL = "RFQs"' in source
	assert 'const RFQ_HISTORY_LABEL = "RFQ History"' in source
	assert 'button.textContent = __(RFQ_HISTORY_LABEL)' in source
	assert 'button.setAttribute("data-retailedge-rfq-history", "true")' in source
	assert "OPEN_RFQ_HISTORY_EVENT" in source
	assert "event.stopImmediatePropagation()" in source


def test_rfq_history_overlay_has_smart_scope_filters_and_sorting():
	overlay = _read(OVERLAY)
	assert "get_request_for_quotation_history" in overlay
	assert "EdgeLinkField" in overlay
	assert "companySearch" in overlay
	assert "branchSearch" in overlay
	assert "supplierSearch" in overlay
	assert "onCompanySelected" in overlay
	assert "this.filters.branch = \"\"" in overlay
	assert "sortBy('name')" in overlay
	assert "sortBy('transaction_date')" in overlay
	assert "sortBy('status')" in overlay
	assert "sortBy('item_count')" in overlay


def test_rfq_rows_are_not_disguised_native_links_and_advanced_access_is_explicit():
	overlay = _read(OVERLAY)
	assert "<strong>{{ row.name }}</strong>" in overlay
	assert "@click=\"openAdvanced(row.name)\"" in overlay
	assert "Advanced: Open in ERPNext" in overlay
	assert "Advanced: RFQs in ERPNext" in overlay
	assert "nativeFallbackEnabled" in overlay
	assert 'const ACCESS_MODE = "edgesuite_only"' in overlay
	assert 'frappe.set_route("Form", "Request for Quotation", name)' in overlay
	assert 'frappe.set_route("List", "Request for Quotation")' in overlay
