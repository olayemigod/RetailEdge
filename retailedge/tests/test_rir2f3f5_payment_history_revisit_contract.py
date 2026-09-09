from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "payment_history.py"
PAGE = ROOT / "public" / "js" / "payment_management" / "PaymentManagement.vue"


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
	assert "get_customer_payment_submit_preview" in source
	assert "get_supplier_payment_submit_preview" in source
	assert '"standard_customer"' in source
	assert '"standard_supplier"' in source
	assert '"advanced_only"' in source


def test_payment_management_owns_history_and_revisit_without_forced_native_handoff():
	page = _read(PAGE)
	assert "Payment History" in page
	assert "retailedge.payment_history.list_payment_history" in page
	assert "retailedge.payment_history.get_payment_history_detail" in page
	assert "paymentHistory" in page
	assert "paymentDetail" in page
	assert "loadPaymentHistory" in page
	assert "reviewHistoryPayment" in page
	assert "canUseNativeDesk" in page
	assert 'v-if="canUseNativeDesk"' in page


def test_history_filters_cover_operational_revisit_dimensions():
	page = _read(PAGE)
	for token in (
		"party_type",
		"party",
		"payment_type",
		"docstatus",
		"from_date",
		"to_date",
	):
		assert token in page
