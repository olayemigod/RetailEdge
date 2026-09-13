from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/stock_position/StockPositionReport.vue"
BACKEND = ROOT / "replenishment_handoff.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_stock_position_native_access_fails_closed_and_uses_final_context():
	source = _read(COMPONENT)
	assert "canUseNativeDesk: false" in source
	assert "this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);" in source


def test_stock_position_native_affordances_require_native_desk():
	source = _read(COMPONENT)
	assert 'clickable: this.canUseNativeDesk && (column.fieldname === "item_code"' in source
	assert 'column.fieldname === "replenishment_status" && this.canCreateMaterialRequest' in source
	assert 'v-if="canUseNativeDesk && canCreateMaterialRequest"' in source


def test_stock_position_native_handoffs_are_defensively_guarded():
	source = _read(COMPONENT)
	assert 'if ((item.target_type === "DocType" || item.target_type === "Report") && !this.canUseNativeDesk) return;' in source
	assert "if (!this.canUseNativeDesk) return;" in source
	assert "if (!this.canUseNativeDesk || !itemCode || !this.canCreateMaterialRequest || this.handoffLoadingItem) return;" in source
	assert "if (!this.canUseNativeDesk) return;" in source
	assert 'openItem(itemCode) { if (this.canUseNativeDesk && itemCode) frappe.set_route("Form", "Item", itemCode); }' in source


def test_stock_position_preserves_server_replenishment_authority():
	frontend = _read(COMPONENT)
	backend = _read(BACKEND)
	assert '"retailedge.operating_report_defaults.get_replenishment_material_request_handoff"' in frontend
	assert 'frappe.has_permission("Material Request", "create")' in backend
	assert "_resolve_warehouse_scope(resolved_filters)" in backend
	assert "_load_direct_reorder_rules" in backend
	assert "_due_rule_payloads" in backend
	assert '"handoff_mode": "unsaved_native_form"' in backend


def test_stock_position_containment_does_not_add_posting_or_permission_bypasses():
	frontend = _read(COMPONENT)
	for forbidden in (
		"frappe.db.commit(",
		"ignore_permissions",
		".submit(",
		".cancel(",
	):
		assert forbidden not in frontend
