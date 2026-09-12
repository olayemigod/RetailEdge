from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "public/js/business_control_center/BusinessControlCenter.vue"
ROW = ROOT / "public/js/business_control_center/BusinessControlRow.vue"
DETAILS = ROOT / "public/js/business_control_center/OwnerControlDetails.vue"


def test_parent_reads_and_propagates_native_desk_capability():
	source = PARENT.read_text(encoding="utf-8")
	assert "canUseNativeDesk: false" in source
	assert "Boolean(navigation.access?.can_use_native_desk)" in source
	assert ':canOpen="canOpenWorkflow(item)"' in source
	assert ':canOpenNative="canUseNativeDesk"' in source


def test_workflow_and_shell_routes_fail_closed():
	source = PARENT.read_text(encoding="utf-8")
	assert 'canOpenWorkflow(item) { return !["DocType", "Report"].includes(item?.target_type) || this.canUseNativeDesk; }' in source
	assert "if (!this.canOpenWorkflow(item)) return" in source
	assert '["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk' in source


def test_control_row_preserves_truth_and_marks_advanced_workflow():
	source = ROW.read_text(encoding="utf-8")
	assert "canOpen: { type: Boolean, default: true }" in source
	assert ':disabled="!canOpen"' in source
	assert "Advanced workflow" in source
	assert "Advanced Native Desk access is required" in source
	assert "Why this is prioritised" in source


def test_invoice_details_remain_visible_but_native_open_fails_closed():
	source = DETAILS.read_text(encoding="utf-8")
	assert "canOpenNative: { type: Boolean, default: false }" in source
	assert source.count(':disabled="!canOpenNative"') == 2
	assert "if (!this.canOpenNative) return" in source
	assert "row.invoice" in source
	assert "row.outstanding" in source
