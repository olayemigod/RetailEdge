from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/daily_sales_audit/DailySalesAuditReport.vue"
DOC = ROOT.parent / "docs/rir2f3f24_daily_sales_audit_native_detail_containment.md"


def _source() -> str:
	return COMPONENT.read_text(encoding="utf-8")


def test_daily_sales_audit_consumes_final_access_context_fail_closed():
	source = _source()
	assert "canUseNativeDesk: false" in source
	assert "this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);" in source
	assert "retailedge.master_experience.get_retailedge_business_hub_context" in source
	assert "retailedge.edgesuite_ui.get_retailedge_business_hub_context" not in source


def test_native_detail_columns_require_native_desk():
	source = _source()
	assert 'clickable: this.canUseNativeDesk && ["name", "cashier", "pos_profile", "pos_opening_shift", "pos_closing_shift", "submitted_for_review_by", "approved_by", "rejected_by"].includes(column.fieldname)' in source
	assert "handleCellClick(payload) { if (!this.canUseNativeDesk) return;" in source
	for target in (
		'frappe.set_route("Form", "RetailEdge Daily Sales Audit", value)',
		'frappe.set_route("Form", "User", value)',
		'frappe.set_route("Form", "POS Profile", value)',
		'frappe.set_route("Form", "POS Opening Shift", value)',
		'frappe.set_route("Form", "POS Closing Shift", value)',
	):
		assert target in source


def test_generic_native_navigation_is_defensively_gated():
	source = _source()
	assert 'if ((item.target_type === "Report" || item.target_type === "DocType") && !this.canUseNativeDesk) return;' in source


def test_slice_does_not_change_audit_or_scope_backends():
	doc = DOC.read_text(encoding="utf-8")
	assert "No Daily Sales Audit backend file is changed" in doc
	assert "B4B5 read/context scope remains unchanged" in doc
	assert "B4B9 register scope remains unchanged" in doc
