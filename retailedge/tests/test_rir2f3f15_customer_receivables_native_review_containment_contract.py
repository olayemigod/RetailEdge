from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/customer_receivables/CustomerReceivablesReport.vue"
ACTIONS = ROOT / "receivables_actions.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_customer_receivables_fails_closed_on_final_native_desk_context():
	source = _read(COMPONENT)
	assert "canUseNativeDesk: false" in source
	assert "this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);" in source


def test_native_detail_and_collection_action_columns_are_capability_gated():
	source = _read(COMPONENT)
	assert "clickable: this.canUseNativeDesk && clickable.includes(column.fieldname)" in source
	assert 'if (this.canUseNativeDesk && this.rows.some((row) => row.payment_request_action))' in source
	assert 'if (this.canUseNativeDesk && this.rows.some((row) => row.dunning_action))' in source


def test_collection_action_fails_before_post_without_native_desk():
	source = _read(COMPONENT)
	assert "if (!this.canUseNativeDesk || !row?.invoice || this.actionInvoice) return;" in source
	assert 'callPostMethod(method, { invoice_name: row.invoice })' in source
	assert source.index("if (!this.canUseNativeDesk || !row?.invoice || this.actionInvoice) return;") < source.index('callPostMethod(method, { invoice_name: row.invoice })')


def test_native_menu_and_report_cell_handoffs_fail_closed():
	source = _read(COMPONENT)
	assert 'if ((item.target_type === "DocType" || item.target_type === "Report") && !this.canUseNativeDesk) return;' in source
	assert 'async openReportCell(payload) {' in source
	assert 'if (!this.canUseNativeDesk) return;' in source
	assert 'frappe.set_route("Form", "Sales Invoice", value)' in source
	assert 'frappe.set_route("Form", "Customer", value)' in source
	assert 'frappe.set_route("Form", "Payment Request", value)' in source
	assert 'frappe.set_route("Form", "Dunning", value)' in source


def test_backend_collection_safety_remains_intact():
	source = _read(ACTIONS)
	for contract in (
		'_assert_invoice_scope(invoice)',
		'frappe.has_permission("Payment Request", "create", throw=True)',
		'frappe.has_permission("Dunning", "create", throw=True)',
		"submit_doc=0",
		"payment_request.insert()",
		"dunning.insert()",
	):
		assert contract in source
	for forbidden in (
		"payment_request.submit()",
		"dunning.submit()",
		"invoice.save(",
		"invoice.db_set(",
		"frappe.db.commit",
	):
		assert forbidden not in source
