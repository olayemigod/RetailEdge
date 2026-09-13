from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "public/js"
OPERATING = ROOT / "operating_context/OperatingContext.vue"
SETUP = ROOT / "retailedge_setup/RetailEdgeSetup.vue"
BRANCH_SETUP = ROOT / "branch_setup/BranchSetup.vue"
ASSIGNMENTS = ROOT / "branch_assignments/BranchAssignments.vue"
FILES = (OPERATING, SETUP, BRANCH_SETUP, ASSIGNMENTS)


def test_context_and_setup_pages_consume_capability_and_guard_shell_routes():
	for path in FILES:
		source = path.read_text(encoding="utf-8")
		assert "canUseNativeDesk: false" in source, path
		assert "Boolean(navigation.access?.can_use_native_desk)" in source, path
		assert '["DocType", "Report"].includes(item.target_type)' in source, path
		assert "!this.canUseNativeDesk" in source, path


def test_retailedge_setup_keeps_edgesuite_managers_and_contains_native_resources():
	source = SETUP.read_text(encoding="utf-8")
	assert "Advanced: Add New" in source
	assert "resourceActionLabel(resource)" in source
	assert 'resource?.manager !== "expense-categories"' in source
	assert "if (!resource?.doctype || !this.canUseNativeDesk) return" in source
	assert "if (!this.canUseNativeDesk) return" in source
	assert 'this.openExpenseCategoryManager("list")' in source
	assert 'frappe.set_route("operating-context")' in source


def test_branch_admin_edgesuite_flows_remain_and_native_full_forms_fail_closed():
	branch_setup = BRANCH_SETUP.read_text(encoding="utf-8")
	assignments = ASSIGNMENTS.read_text(encoding="utf-8")
	for source in (branch_setup, assignments):
		assert "Advanced: Full Form" in source
		assert ':disabled="!canUseNativeDesk"' in source
	assert "if (this.canUseNativeDesk && name) window.open" in branch_setup
	assert "if (this.canUseNativeDesk && row?.name) window.open" in assignments
	assert 'frappe.set_route("branch-assignments")' in branch_setup
	assert 'frappe.set_route("branch-setup")' in assignments
