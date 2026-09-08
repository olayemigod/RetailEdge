from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_purchase_receipt.py"
OVERLAY = ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchaseReceiptPreviewOverlay.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _submit_function(source: str) -> str:
	return source.split("def submit_standard_purchase_receipt", 1)[1]


def test_standard_submit_is_post_only_locked_and_stale_safe():
	source = _read(BACKEND)
	submit = _submit_function(source)
	assert '@frappe.whitelist(methods=["POST"])' in source.split("def submit_standard_purchase_receipt", 1)[0][-120:]
	assert "_get_purchase_order_for_receipt(purchase_order, lock=True)" in submit
	assert '"SELECT name FROM `tabPurchase Order` WHERE name = %s FOR UPDATE"' in source
	assert "_assert_receipt_permissions(require_submit=True)" in submit
	assert "expected_purchase_order_modified" in submit
	assert "expected_modified != current_modified" in submit
	assert "Refresh the preview before posting" in submit


def test_server_rechecks_standard_eligibility_before_erpnext_submit():
	source = _read(BACKEND)
	submit = _submit_function(source)
	for contract in (
		"_validate_open_po(po)",
		"_validate_po_scope(po)",
		"_map_receipt(po, branch)",
		"if blockers:",
		"requires Advanced ERPNext handling",
	):
		assert contract in submit
	assert submit.index("if blockers:") < submit.index("receipt.insert()") < submit.index("receipt.submit()")


def test_standard_mapping_fails_closed_on_receiving_warehouse_context():
	source = _read(BACKEND)
	assert '"missing_warehouse"' in source
	assert 'frappe.db.get_value("Warehouse", warehouse, "company")' in source
	assert "does not belong to Company" in source
	assert "_transaction_branch_field(PURCHASE_RECEIPT_DOCTYPE)" in source
	assert "setattr(receipt, receipt_branch_field, branch)" in source


def test_posting_keeps_erpnext_as_stock_truth_without_permission_bypass():
	source = _read(BACKEND)
	submit = _submit_function(source)
	assert "receipt.insert()" in submit
	assert "receipt.submit()" in submit
	assert '"stock_posted_by": "ERPNext Purchase Receipt submit"' in submit
	assert "ignore_permissions=True" not in submit
	assert 'frappe.new_doc("Stock Ledger Entry")' not in submit
	assert 'frappe.new_doc("GL Entry")' not in submit
	assert ".db_set(" not in submit


def test_edgesuite_post_action_requires_standard_eligibility_and_submit_permission():
	overlay = _read(OVERLAY)
	assert 'const SUBMIT_METHOD = "retailedge.professional_purchase_receipt.submit_standard_purchase_receipt"' in overlay
	assert "this.preview?.standard_receipt_eligible && this.preview?.can_submit" in overlay
	assert "v-if=\"canSubmitStandard\"" in overlay
	assert "Receive Stock" in overlay
	assert "frappe.confirm(" in overlay
	assert "expected_purchase_order_modified: this.preview?.purchase_order_modified" in overlay
	assert '}, "POST")' in overlay


def test_advanced_receipt_handoff_remains_separate_from_standard_posting():
	overlay = _read(OVERLAY)
	assert "nativeFallbackEnabled" in overlay
	assert "Advanced: Prepare in ERPNext" in overlay
	assert "retailedge-advanced-prepare-purchase-receipt" in overlay
	assert "This receipt contains stock controls that RetailEdge will not simplify or bypass." in overlay
