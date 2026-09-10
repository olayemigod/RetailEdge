from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/purchase_reporting/PurchaseReportingReport.vue"
BACKEND = ROOT / "purchase_reporting.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_purchase_reporting_fails_closed_on_final_native_desk_context():
	source = _read(COMPONENT)
	assert "canUseNativeDesk: false" in source
	assert "this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);" in source


def test_native_detail_clickability_is_gated_but_edgesuite_payment_stays_operational():
	source = _read(COMPONENT)
	assert 'clickable: this.canUseNativeDesk && ["invoice", "supplier", "return_against"].includes(column.fieldname)' in source
	assert 'columns.push({ label: "Payment", fieldname: "payment_action", fieldtype: "Data", width: 110, clickable: true });' in source


def test_menu_and_report_cell_native_handoffs_fail_closed():
	source = _read(COMPONENT)
	assert 'if ((item.target_type === "DocType" || item.target_type === "Report") && !this.canUseNativeDesk) return;' in source
	assert 'if (column.fieldname === "payment_action") { this.openSupplierPayment(row); return; }' in source
	assert 'if (!this.canUseNativeDesk) return;' in source
	assert 'frappe.set_route("Form", "Purchase Invoice", value)' in source
	assert 'frappe.set_route("Form", "Supplier", value)' in source


def test_native_payment_fallback_remains_explicitly_guarded():
	source = _read(COMPONENT)
	assert 'openNativePayment() { if (!this.canUseNativeDesk) return;' in source


def test_slice_does_not_require_backend_semantic_change():
	source = _read(BACKEND)
	for forbidden in (
		"ignore_permissions=True",
		"frappe.db.commit()",
	):
		assert forbidden not in source
