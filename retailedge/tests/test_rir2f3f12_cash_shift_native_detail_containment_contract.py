from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/cash_shift_verification/CashShiftVerificationReport.vue"


def _source() -> str:
	return COMPONENT.read_text(encoding="utf-8")


def test_cash_shift_native_detail_access_fails_closed_and_uses_final_context():
	source = _source()
	assert "canUseNativeDesk: false" in source
	assert "this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);" in source


def test_cash_shift_native_detail_columns_are_not_clickable_without_native_desk():
	source = _source()
	assert "clickable: this.canUseNativeDesk && [" in source
	for fieldname in (
		"daily_sales_audit",
		"cashier",
		"pos_profile",
		"opening_shift",
		"closing_shift",
	):
		assert f'"{fieldname}"' in source


def test_cash_shift_native_detail_routes_are_guarded():
	source = _source()
	assert "if (!this.canUseNativeDesk) return;" in source
	assert 'if ((item.target_type === "DocType" || item.target_type === "Report") && !this.canUseNativeDesk) return;' in source
	assert 'frappe.set_route("Form", "RetailEdge Daily Sales Audit", value);' in source
	assert 'frappe.set_route("Form", "POS Profile", value);' in source


def test_cash_shift_containment_does_not_add_posting_shortcuts():
	source = _source()
	for forbidden in (
		"frappe.db.commit(",
		"ignore_permissions",
		".submit(",
		".cancel(",
	):
		assert forbidden not in source
