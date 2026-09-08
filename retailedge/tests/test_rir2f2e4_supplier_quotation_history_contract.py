from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_supplier_quotation.py"
BUNDLE = ROOT / "public" / "js" / "professional_purchasing.bundle.js"
OVERLAY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalSupplierQuotationHistoryOverlay.vue"
GUARD = ROOT / "public" / "js" / "retailedge_edgesuite_only_operational_guard.bundle.js"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_supplier_quotation_history_is_permission_aware_bounded_and_read_only():
	source = _read(BACKEND)
	assert "def get_supplier_quotation_history(" in source
	assert "_assert_read(SUPPLIER_QUOTATION_DOCTYPE)" in source
	assert "frappe.get_list(" in source
	assert "MAX_SUPPLIER_QUOTATION_HISTORY = 100" in source
	assert "max(1, min(cint(limit) or 50, MAX_SUPPLIER_QUOTATION_HISTORY))" in source
	assert "frappe.new_doc(" not in source
	assert ".insert(" not in source
	assert ".submit(" not in source
	assert "ignore_permissions=True" not in source


def test_restricted_or_branch_filtered_history_fails_closed_through_permitted_rfqs():
	source = _read(BACKEND)
	assert "elif resolved_branch or not global_access:" in source
	assert "_permitted_rfq_names(" in source
	assert "_supplier_quotation_names_from_rfqs(permitted_rfqs)" in source
	assert 'filters["name"] = ["in", candidate_names or ["__no_permitted_supplier_quotation__"]]' in source
	assert '"excluded_without_attributable RFQ"' in source
	assert "_branch_scoped_filters(" in source


def test_child_reference_enrichment_does_not_leak_unreadable_rfq_names():
	source = _read(BACKEND)
	assert "readable_rfqs = set(branch_by_rfq)" in source
	assert "rfqs_by_parent[parent] = [rfq for rfq in rfqs_by_parent[parent] if rfq in readable_rfqs]" in source
	assert "frappe.get_list(" in source
	assert 'filters={"name": ["in", sorted(linked_rfqs)]}' in source


def test_supplier_quotation_history_uses_smart_company_branch_supplier_filters():
	overlay = _read(OVERLAY)
	assert "EdgeLinkField" in overlay
	assert 'v-model="filters.company"' in overlay
	assert 'v-model="filters.branch"' in overlay
	assert 'v-model="filters.supplier"' in overlay
	assert 'kind, txt, company: this.filters.company || null' in overlay
	assert 'limit: 50' in overlay
	assert "sortBy('grand_total')" in overlay
	assert "sortBy('valid_till')" in overlay


def test_supplier_quotation_button_is_capture_intercepted_into_edgesuite_history():
	bundle = _read(BUNDLE)
	assert 'const SUPPLIER_QUOTATIONS_LABEL = "Supplier Quotations"' in bundle
	assert 'const SUPPLIER_QUOTATION_HISTORY_LABEL = "Supplier Quote History"' in bundle
	assert 'const OPEN_SUPPLIER_QUOTATION_HISTORY_EVENT = "retailedge-open-professional-supplier-quotation-history"' in bundle
	assert 'button.setAttribute("data-retailedge-supplier-quotation-history", "true")' in bundle
	assert "event.preventDefault()" in bundle
	assert "event.stopPropagation()" in bundle
	assert "event.stopImmediatePropagation()" in bundle
	assert "OPEN_SUPPLIER_QUOTATION_HISTORY_EVENT" in bundle
	assert "ProfessionalSupplierQuotationHistoryOverlay" in bundle


def test_native_supplier_quotation_access_is_explicit_advanced_only():
	overlay = _read(OVERLAY)
	guard = _read(GUARD)
	assert 'const ACCESS_MODE = "edgesuite_only"' in overlay
	assert "nativeFallbackEnabled" in overlay
	assert "Advanced: Open in ERPNext" in overlay
	assert "Advanced: Supplier Quotations in ERPNext" in overlay
	assert 'frappe.set_route("Form", "Supplier Quotation", name)' in overlay
	assert 'frappe.set_route("List", "Supplier Quotation")' in overlay
	assert '"Supplier Quotation",' in guard
	assert '"supplier-quotation",' in guard


def test_supplier_quotation_comparison_remains_explicit_advanced_native_action():
	bundle = _read(BUNDLE)
	assert 'const COMPARE_QUOTATIONS_LABEL = "Compare Quotations"' in bundle
	assert 'const ADVANCED_COMPARE_QUOTATIONS_LABEL = "Advanced: Compare Quotations in ERPNext"' in bundle
	assert "if (!nativeDeskEnabled())" in bundle
	assert 'button.setAttribute("data-retailedge-advanced-native", "Supplier Quotation Comparison")' in bundle
