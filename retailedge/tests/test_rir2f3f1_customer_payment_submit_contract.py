from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "standard_customer_payment_submit.py"
PAGE = ROOT / "public" / "js" / "payment_management" / "PaymentManagement.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str, next_name: str | None = None) -> str:
	start = source.index(f"def {name}(")
	if next_name:
		end = source.index(f"def {next_name}(", start + 1)
		return source[start:end]
	return source[start:]


def test_preview_is_read_only_scoped_and_exposes_submit_blockers():
	source = _read(BACKEND)
	preview = _function_source(source, "get_customer_payment_submit_preview", "list_standard_customer_payment_drafts")
	assert "_build_preview" in preview
	assert '"persistence": "none"' in source
	assert '"blockers": blockers' in source
	assert '"can_submit": not blockers' in source
	assert "doc.submit(" not in preview
	assert "doc.save(" not in preview
	assert "frappe.db.commit" not in source


def test_draft_listing_is_permission_aware_and_requires_operating_scope():
	source = _read(BACKEND)
	listing = _function_source(source, "list_standard_customer_payment_drafts", "submit_standard_customer_payment")
	assert "Choose Company and Customer before reviewing draft payments" in listing
	assert "Choose a Branch before reviewing draft payments for restricted access" in listing
	assert "validate_user_branch_access(" in listing
	assert "user_has_global_branch_access(user=frappe.session.user)" in listing
	assert "frappe.get_list(" in listing
	assert '"docstatus": 0' in listing
	assert '"payment_type": "Receive"' in listing
	assert '"party_type": CUSTOMER_DOCTYPE' in listing
	assert "frappe.get_all(" not in listing


def test_standard_shape_excludes_supplier_pay_transfer_multicurrency_and_complex_allocations():
	source = _read(BACKEND)
	assert '!= "Receive"' in source
	assert '!= CUSTOMER_DOCTYPE' in source
	assert "Pay or Internal Transfer" in source
	assert "Multi-currency Payment Entries require Advanced ERPNext review" in source
	assert "Payments allocated to multiple documents require Advanced ERPNext review" in source
	assert "Only a single Sales Invoice allocation is supported" in source
	assert "Return Sales Invoices require Advanced ERPNext review" in source
	assert "Payments with deductions or exchange differences require Advanced ERPNext review" in source
	assert "Separate party-account advances require Advanced ERPNext review" in source


def test_restricted_blank_branch_and_context_tampering_fail_closed():
	source = _read(BACKEND)
	assert "_payment_branch(doc)" in source
	assert "user_has_global_branch_access(user=frappe.session.user)" in source
	assert "validate_user_branch_access(" in source
	assert "has no Branch attribution for your restricted access" in source
	assert "does not belong to the selected Company" in source
	assert "does not belong to the selected Customer" in source
	assert "does not belong to the selected Branch" in source


def test_submit_is_post_only_locked_stale_safe_and_erpnext_authoritative():
	source = _read(BACKEND)
	submit = _function_source(source, "submit_standard_customer_payment")
	assert '@frappe.whitelist(methods=["POST"])' in source
	assert "FOR UPDATE" in submit
	assert "expected_payment_entry_modified" in submit
	assert "changed after the review" in submit
	assert "_standard_submit_blockers(doc, payment_branch)" in submit
	assert "doc.submit()" in submit
	assert "doc.reload()" in submit
	assert "ignore_permissions=True" not in submit
	assert "frappe.db.commit" not in source
	assert 'frappe.new_doc("GL Entry")' not in source
	assert 'frappe.new_doc("Payment Ledger Entry")' not in source
	assert "db_set(" not in source
	assert '"source_of_truth": "ERPNext Payment Entry submit"' in submit


def test_payment_management_reviews_and_submits_without_forced_native_handoff():
	page = _read(PAGE)
	assert "Draft Payments Awaiting Submission" in page
	assert "list_standard_customer_payment_drafts" in page
	assert "get_customer_payment_submit_preview" in page
	assert "submit_standard_customer_payment" in page
	assert "expected_payment_entry_modified" in page
	assert "Submit Payment" in page
	assert "Open in ERPNext" in page
	assert "Create Draft Receipt" in page
	assert "Customer advance draft created. Review it below before submission." in page
	advance_creation = page[page.index("async openAdvanceDialog"):page.index("openPaymentEntries()")]
	assert 'frappe.set_route("Form", "Payment Entry", result.name)' not in advance_creation


def test_context_changes_clear_draft_review_and_submission_refreshes_authoritative_state():
	page = _read(PAGE)
	assert "clearDraftState()" in page
	assert "onCompanySelected(option)" in page
	assert "onBranchSelected(option)" in page
	assert "onCustomerSelected(option)" in page
	assert "await this.loadDraftPayments()" in page
	assert "await this.loadSettlementInvoice(result.sales_invoice)" in page
	assert "await this.loadAdvances()" in page
