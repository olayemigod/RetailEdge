from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "public/js/action_center/ActionCenter.vue"


def _method_block(source: str, name: str, size: int = 1500) -> str:
	start = source.index(f"\t\t{name}(")
	return source[start : start + size]


def test_action_centre_reads_native_desk_capability():
	source = PAGE.read_text(encoding="utf-8")
	assert "canUseNativeDesk: false" in source
	assert "Boolean(navigation.access?.can_use_native_desk)" in source


def test_native_workflow_action_remains_visible_but_disabled():
	source = PAGE.read_text(encoding="utf-8")
	assert source.count(':disabled="!canOpenWorkflow(item)"') == 2
	assert source.count('Advanced workflow') >= 2
	block = _method_block(source, "canOpenWorkflow")
	assert '["DocType", "Report"].includes(item?.target_type)' in block
	assert "this.canUseNativeDesk" in block


def test_workflow_and_shell_navigation_fail_closed():
	source = PAGE.read_text(encoding="utf-8")
	workflow = _method_block(source, "openWorkflow")
	assert "if (!this.canOpenWorkflow(item)) return" in workflow
	navigation = _method_block(source, "handleNavigation")
	assert '["DocType", "Report"].includes(item.target_type)' in navigation
	assert "!this.canUseNativeDesk" in navigation


def test_exception_truth_and_follow_up_controls_remain():
	source = PAGE.read_text(encoding="utf-8")
	for contract in (
		"Why this is prioritised",
		'@click="acknowledge(item)"',
		'@click="promptAssignment(item)"',
		'@click="promptSchedule(item)"',
		'@click="promptSnooze(item)"',
	):
		assert contract in source
