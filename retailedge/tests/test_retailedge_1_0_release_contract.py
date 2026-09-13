from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


def test_retailedge_1_0_version_is_frozen_in_package_metadata():
	source = (APP_ROOT / "__init__.py").read_text(encoding="utf-8")
	assert '__version__ = "1.0.0"' in source


def test_retailedge_1_0_release_documents_exist_and_are_linked():
	readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
	for relative_path in (
		"docs/retailedge_1_0_install_upgrade.md",
		"docs/retailedge_1_0_release_notes.md",
		"docs/retailedge_1_0_release_checklist.md",
	):
		assert (REPO_ROOT / relative_path).exists()
		assert relative_path in readme


def test_rc3_is_frozen_before_1_0_release_hardening():
	runbook = (REPO_ROOT / "docs" / "rir2e_consolidated_browser_persona_qa.md").read_text(encoding="utf-8")
	assert "PASS — RC3 FROZEN" in runbook
	assert "21 / 21 PASS" in runbook


def test_release_checklist_keeps_tag_on_promoted_release_branch():
	checklist = (REPO_ROOT / "docs" / "retailedge_1_0_release_checklist.md").read_text(encoding="utf-8")
	assert "version-16" in checklist
	assert "Do not create v1.0.0 directly on the QA working branch." in checklist
