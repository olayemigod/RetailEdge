from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "standard_customer_payment_submit.py"
DIALOG = ROOT / "public" / "js" / "retailedge_business_hub" / "SimplePaymentDialog.vue"
HUB = ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _method_source(source: str, name: str, next_name: str) -> str:
	start = source.index(f"\t\t{name}(")
	end = source.index(f"\t\t{next_name}(", start + 1)
	return source[start:end]


def test_business_hub_customer_payment_reuses_f3f1_review_and_submit_service():
	dialog = _read(DIALOG)
	assert "Customer Payment Review" in dialog
	assert "standard_customer_payment_submit.get_customer_payment_submit_preview" in dialog
	assert "standard_customer_payment_submit.submit_standard_customer_payment" in dialog
	assert 'this.intent === "receive-customer-payment"' in dialog
	assert "expected_payment_entry_modified: this.customerReview.payment_entry_modified" in dialog
	assert "customer: this.customerReview.customer" in dialog
	assert "Submit Payment" in dialog
	assert "Open in ERPNext" in dialog


def test_customer_draft_stays_in_edgesuite_for_review_instead_of_emitting_saved():
	dialog = _read(DIALOG)
	save = _method_source(dialog, "async saveDraft", "formatAmount")
	customer_branch = save[save.index("if (this.isCustomerPayment)"):save.index("if (this.isSupplierPayment)", save.index("if (this.isCustomerPayment)"))]
	assert "await this.loadCustomerReview(result.name);" in customer_branch
	assert "return;" in customer_branch
	assert 'this.$emit("saved", result);' not in customer_branch
	assert 'frappe.set_route("Form", "Payment Entry", result.name)' not in save


def test_customer_submit_is_explicit_stale_safe_and_does_not_force_native_navigation():
	dialog = _read(DIALOG)
	submit = _method_source(dialog, "async submitCustomerPayment", "async submitSupplierPayment")
	assert "frappe.confirm(" in dialog
	assert "CUSTOMER_SUBMIT_METHOD" in submit
	assert "expected_payment_entry_modified" in submit
	assert 'this.$emit("close");' in submit
	assert 'frappe.set_route("Form", "Payment Entry"' not in submit



def test_native_payment_entry_navigation_is_an_explicit_advanced_fallback_only():
	dialog = _read(DIALOG)
	open_native = _method_source(dialog, "openReviewedCustomerPaymentInERPNext", "openReviewedPaymentInERPNext")
	assert 'frappe.set_route("Form", "Payment Entry", paymentEntry);' in open_native
	assert "Advanced ERPNext" in dialog
	assert "nativeFallbackEnabled" in open_native


def test_customer_review_preserves_standard_backend_accounting_authority():
	backend = _read(BACKEND)
	assert '@frappe.whitelist(methods=["POST"])' in backend
	assert "FOR UPDATE" in backend
	assert "doc.submit()" in backend
	assert "doc.reload()" in backend
	assert "frappe.db.commit" not in backend
	assert "db_set(" not in backend
	assert '"source_of_truth": "ERPNext Payment Entry submit"' in backend


def test_business_hub_still_uses_one_guided_payment_dialog_for_receive_and_pay_supplier():
	hub = _read(HUB)
	assert 'const GUIDED_PAYMENT_ACTIONS = new Set(["receive-customer-payment", "pay-supplier"]);' in hub
	assert ":intent=\"simplePaymentIntent\"" in hub
	assert "GUIDED_PAYMENT_ACTIONS.has(action.key)" in hub
