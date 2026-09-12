from __future__ import annotations

from pathlib import Path


SOURCE = (
	Path(__file__).resolve().parents[1]
	/ "public/js/project_operations/ProjectOperations.vue"
)


def test_project_operations_consumes_native_desk_capability_and_guards_shell_routes():
	source = SOURCE.read_text(encoding="utf-8")
	assert "canUseNativeDesk: false" in source
	assert "Boolean(navigation.access?.can_use_native_desk)" in source
	assert 'item.target_type === "Report" || item.target_type === "DocType"' in source
	assert "&& !this.canUseNativeDesk" in source


def test_project_operations_keeps_identity_visible_but_native_details_capability_gated():
	source = SOURCE.read_text(encoding="utf-8")
	for identity in (
		"row.subject",
		"row.name",
		"context.timeline",
		"context.project_cash_in_rows",
		"context.project_cash_out_rows",
	):
		assert identity in source
	assert 'v-if="canUseNativeDesk"' in source
	assert 'v-else>{{ row.subject }}</span>' in source
	assert 'v-else>{{ row.name }}</span>' in source


def test_project_operations_advanced_header_actions_and_handlers_fail_closed():
	source = SOURCE.read_text(encoding="utf-8")
	for label in (
		"Advanced: Open Project",
		"Advanced: Open Tasks",
		"Advanced: New Task",
		"Advanced: Open Budgets",
		"Advanced: New Budget",
		"Advanced: Financial Control",
		"Advanced: Spend & Materials",
		"Advanced: Record Project Receipt",
	):
		assert label in source
	for method_guard in (
		"openReceiptDialog() { if (!this.canUseNativeDesk) return;",
		"async openCostDialog() { if (!this.canUseNativeDesk) return;",
		"openProject() { if (!this.canUseNativeDesk) return;",
		"openProjectTasks() { if (!this.canUseNativeDesk) return;",
		"newTask() { if (!this.canUseNativeDesk) return;",
		"openTask(name) { if (!this.canUseNativeDesk) return;",
		"openProjectBudgets() { if (!this.canUseNativeDesk) return;",
		"newBudget() { if (!this.canUseNativeDesk) return;",
		"openBudget(name) { if (!this.canUseNativeDesk) return;",
		"openFinancialControl() { if (!this.canUseNativeDesk) return;",
		"openPayment(name) { if (!this.canUseNativeDesk) return;",
		"openTimelineDoc(row) { if (!this.canUseNativeDesk) return;",
	):
		assert method_guard in source
