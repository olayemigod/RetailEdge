from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "standard_supplier_payment_submit.py"
DIALOG = ROOT / "public" / "js" / "retailedge_business_hub" / "SimplePaymentDialog.vue"


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
	preview = _function_source(source, "get_supplier_payment_submit_preview", "list_standard_supplier_payment_drafts")
	assert "_build_preview" in preview
	assert '"persistence": "none"' in source
	assert '"blockers": blockers' in source
	assert '"can_submit": not blockers' in source
	assert "doc.submit(" not in preview
	assert "doc.save(" not in preview
	assert "frappe.db.commit" not in source


def test_draft_listing_is_permission_aware_and_requires_operating_scope():
	source = _read(BACKEND)
	listing = _function_source(source, "list_standard_supplier_payment_drafts", "submit_standard_supplier_payment")
	assert "Choose Company and Supplier before reviewing draft payments" in listing
	assert "Choose a Branch before reviewing draft payments for restricted access" in listing
	assert "validate_user_branch_access(" in listing
	assert "user_has_global_branch_access(user=frappe.session.user)" in listing
	assert "frappe.get_list(" in listing
	assert '"docstatus": 0' in listing
	assert '"payment_type": "Pay"' in listing
	assert '"party_type": SUPPLIER_DOCTYPE' in listing
	assert "frappe.get_all(" not in listing


def test_standard_shape_is_one_purchase_invoice_company_currency_without_advance_or_complexity():
	source = _read(BACKEND)
	assert '!= "Pay"' in source
	assert '!= SUPPLIER_DOCTYPE' in source
	assert "Only a single Purchase Invoice allocation is supported" in source
	assert "Supplier advances require Advanced ERPNext review" in source
	assert "Payments allocated to multiple documents require Advanced ERPNext review" in source
	assert "Return Purchase Invoices require Advanced ERPNext review" in source
	assert "Multi-currency Purchase Invoice payments require Advanced ERPNext review" in source
	assert "Multi-currency Payment Entries require Advanced ERPNext review" in source
	assert "Standard supplier payment must allocate the full payment to one Purchase Invoice" in source
	assert "Supplier advances or unallocated amounts require Advanced ERPNext review" in source
	assert "Payments with deductions or exchange differences require Advanced ERPNext review" in source
	assert "Standard supplier payment requires a Bank or Cash payment account" in source
	assert "Standard supplier payment requires the Supplier payable account" in source


def test_restricted_blank_branch_and_context_tampering_fail_closed():
	source = _read(BACKEND)
	assert "_payment_branch(doc)" in source
	assert "user_has_global_branch_access(user=frappe.session.user)" in source
	assert "validate_user_branch_access(" in source
	assert "has no Branch attribution for your restricted access" in source
	assert "does not belong to the selected Company" in source
	assert "does not belong to the selected Supplier" in source
	assert "does not belong to the selected Branch" in source


def test_submit_is_post_only_locked_stale_safe_and_erpnext_authoritative():
	source = _read(BACKEND)
	submit = _function_source(source, "submit_standard_supplier_payment")
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


def test_business_hub_supplier_payment_reviews_and_submits_without_forced_native_handoff():
	page = _read(DIALOG)
	assert "get_supplier_payment_submit_preview" in page
	assert "submit_standard_supplier_payment" in page
	assert 'this.intent === "pay-supplier"' in page
	assert "expected_payment_entry_modified" in page
	assert "Submit Payment" in page
	assert "Open in ERPNext" in page
	assert "Standard Pay Supplier supports one Purchase Invoice per payment" in page
	supplier_creation = page[page.index("async saveDraft()"):page.index("formatAmount(value)")]
	assert 'this.$emit("saved", result);' in supplier_creation
	assert "if (this.isSupplierPayment)" in supplier_creation
	assert "await this.loadSupplierReview(result.name);" in supplier_creation
	assert supplier_creation.index("await this.loadSupplierReview(result.name);") < supplier_creation.index(
		'this.$emit("saved", result);'
	)


def test_supplier_submit_stays_standard_and_native_open_is_explicit():
	page = _read(DIALOG)
	assert "async submitSupplierPayment()" in page
	assert "SUPPLIER_SUBMIT_METHOD" in page
	assert "expected_payment_entry_modified: this.supplierReview.payment_entry_modified" in page
	assert "frappe.confirm(" in page
	submit = page[page.index("async submitSupplierPayment()"):page.index("async saveDraft()")]
	assert 'this.$emit("close");' in submit
	assert 'frappe.set_route("Form", "Payment Entry"' not in submit
	assert "frappe.show_alert" not in submit
	assert 'frappe.set_route("Form", "Payment Entry", paymentEntry);' in page
