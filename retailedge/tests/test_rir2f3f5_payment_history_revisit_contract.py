from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "payment_history.py"
PANEL = ROOT / "public" / "js" / "payment_management" / "PaymentHistoryPanel.vue"
MANAGEMENT_BUNDLE = ROOT / "public" / "js" / "payment_management.bundle.js"
MANAGEMENT_LOADER = ROOT / "retailedge" / "page" / "payment_management" / "payment_management.js"
HISTORY_BUNDLE = ROOT / "public" / "js" / "payment_history.bundle.js"
HISTORY_PAGE = ROOT / "public" / "js" / "payment_management" / "PaymentHistoryPage.vue"
HISTORY_LOADER = ROOT / "retailedge" / "page" / "payment_history" / "payment_history.js"
NAVIGATION = ROOT / "edgesuite_ui.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_history_backend_is_permission_aware_bounded_and_branch_safe():
	source = _read(BACKEND)
	assert "get_operational_branch_scope" in source
	assert "validate_operating_branch" in source
	assert "frappe.get_list(" in source
	assert "frappe.get_all(" not in source
	assert "frappe.has_permission" in source
	assert "MAX_PAGE_SIZE" in source
	assert '"__never__"' in source
	assert "allowed_branches" in source
	assert "branch_assignment" in _read(ROOT / "operating_context.py")


def test_history_is_read_only_and_keeps_erpnext_payment_entry_authoritative():
	source = _read(BACKEND)
	assert "list_payment_history" in source
	assert "get_payment_history_detail" in source
	assert '"source_of_truth": "ERPNext Payment Entry"' in source
	assert "doc.save(" not in source
	assert "doc.submit(" not in source
	assert "doc.cancel(" not in source
	assert "frappe.db.commit" not in source
	assert "db_set(" not in source
	assert 'frappe.new_doc("GL Entry")' not in source
	assert 'frappe.new_doc("Payment Ledger Entry")' not in source


def test_detail_reuses_existing_standard_customer_and_supplier_review_contracts():
	source = _read(BACKEND)
	panel = _read(PANEL)
	assert "get_customer_payment_submit_preview" in source
	assert "get_supplier_payment_submit_preview" in source
	assert '"standard_customer"' in source
	assert '"standard_supplier"' in source
	assert '"advanced_only"' in source
	assert "retailedge.standard_customer_payment_submit.submit_standard_customer_payment" in panel
	assert "retailedge.standard_supplier_payment_submit.submit_standard_supplier_payment" in panel
	assert "expected_payment_entry_modified" in panel
	assert "Submit Standard Payment" in panel


def test_payment_history_is_a_separate_edgesuite_page_linked_from_payment_management():
	panel = _read(PANEL)
	management_bundle = _read(MANAGEMENT_BUNDLE)
	management_loader = _read(MANAGEMENT_LOADER)
	history_bundle = _read(HISTORY_BUNDLE)
	history_page = _read(HISTORY_PAGE)
	history_loader = _read(HISTORY_LOADER)
	navigation = _read(NAVIGATION)
	assert "Payment History" in panel
	assert "retailedge.payment_history.list_payment_history" in panel
	assert "retailedge.payment_history.get_payment_history_detail" in panel
	assert "paymentHistory" in panel
	assert "paymentDetail" in panel
	assert "loadPaymentHistory" in panel
	assert "reviewHistoryPayment" in panel
	assert "canUseNativeDesk" in panel
	assert "retailedge.edgesuite_ui.get_retailedge_business_hub_context" in panel
	assert "retailedge.master_experience.get_master_retailedge_business_hub_context" not in panel
	assert 'v-if="canUseNativeDesk && paymentDetail.payment_entry"' in panel
	assert "PaymentHistoryPanel.vue" not in management_bundle
	assert "mountPaymentHistoryPanel" not in management_loader
	assert "PaymentHistoryPage.vue" in history_bundle
	assert "mountPaymentHistoryPage" in history_bundle
	assert 'const PAGE_ROUTE = "payment-history"' in history_loader
	assert "PaymentHistoryPanel" in history_page
	assert '"label": "Payment History"' in navigation
	assert '"target": "payment-history"' in navigation
	assert 'retailedgeConsumeBusinessHubRouteOptions?.("payment-history")' in panel

def test_history_filters_cover_operational_revisit_dimensions_and_smart_party_queries():
	panel = _read(PANEL)
	for token in (
		"party_type",
		"party",
		"payment_type",
		"docstatus",
		"from_date",
		"to_date",
	):
		assert token in panel
	assert "retailedge.customer_receivables.search_customer_receivables_options" in panel
	assert "retailedge.purchase_reporting.search_purchase_reporting_options" in panel
	assert 'this.filters.party_type === "Customer"' in panel
	assert 'kind: "supplier"' in panel


def test_native_payment_open_is_explicit_and_double_gated():
	panel = _read(PANEL)
	assert 'v-if="canUseNativeDesk"' in panel
	assert "if (!this.canUseNativeDesk || !name) return" in panel
	assert 'frappe.set_route("Form", "Payment Entry", name)' in panel


def test_payment_review_opens_in_modal_instead_of_inline_below_history():
	panel = _read(PANEL)
	assert 'const REQUIRED_COMPONENTS = ["EdgeLinkField", "EdgeDropdown", "EdgeModal"]' in panel
	assert ':open="detailOpen"' in panel
	assert "Payment Review ·" in panel
	assert "detailOpen = true" in panel
	assert "payment-detail-panel" not in panel
	assert "payment-review-footer" in panel
	assert "Submit Standard Payment" in panel
	assert "Advanced: ERPNext" in panel
	assert "confirmAboveEdgeModal" in panel
	assert "const paymentEntry = this.paymentDetail.payment_entry;" in panel


def test_submitted_payment_entries_use_view_while_drafts_keep_review():
	panel = _read(PANEL)
	assert 'Number(row.docstatus || 0) === 0 ? "Review" : "View"' in panel
	assert '"Payment Review" : "Payment View"' in panel
	assert ':open="detailOpen"' in panel
	assert "Submitted and cancelled accounting records remain read-only." in panel
	assert "Submit Standard Payment" in panel
