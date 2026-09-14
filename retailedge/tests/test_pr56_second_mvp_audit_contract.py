from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT.parent / "docs/retailedge_mvp_second_audit_pr56_20260914.md"
RC3 = ROOT.parent / "docs/rir2e_consolidated_browser_persona_qa.md"
BROWSER = ROOT.parent / "browser-tests/retailedge_rc3_acceptance.spec.cjs"
HUB_TEST = ROOT / "tests/test_mvp_business_hub_home_contract.py"


def test_pr56_second_audit_has_twelve_area_review_and_governed_release_order():
	source = AUDIT.read_text(encoding="utf-8")
	assert "Authoritative PR: **#56**" in source
	assert "Twelve-area MVP review" in source
	for number in range(1, 13):
		assert f"| {number} |" in source
	assert "Browser/persona runs triggered before this audit is frozen" in source
	assert "Execute formal RC3 browser/persona acceptance on the frozen audit head" in source


def test_pr56_audit_records_and_closes_only_the_identified_p1_contract_gaps():
	source = AUDIT.read_text(encoding="utf-8")
	for token in (
		"P1-A — stale Business Hub acceptance assertion — CLOSED",
		"P1-B — stale RC3 authority — CLOSED",
		"P1-C — missing PR #56 browser regression coverage — CLOSED",
	):
		assert token in source
	assert "No new P0 product, accounting, stock, permission, branch-isolation, install or upgrade defect was found." in source


def test_rc3_contract_is_reset_to_pr56_and_old_pr55_pass_is_historical_only():
	source = RC3.read_text(encoding="utf-8")
	assert "**Authoritative PR:** #56" in source
	assert "qa/retailedge-visual-identity" in source
	assert "**Execution status:** **NOT YET COUNTED FOR PR #56**" in source
	assert "Browser runs triggered before the second MVP audit is frozen" in source
	assert "Historical PR #55 closure decision" in source
	assert "Current PR #56 closure decision: **NOT YET RUN AS FORMAL RC3**" in source


def test_pr56_rc3_browser_spec_covers_business_indices_history_recovery_and_branch_switcher():
	source = BROWSER.read_text(encoding="utf-8")
	for title in (
		"RC3 PR56 Business Hub renders the eight actionable business indices",
		"RC3 PR56 Back and Forward navigation restore the EdgeSuite shell without refresh",
		"RC3 PR56 multi-Branch persona receives the shared working-Branch switcher",
	):
		assert title in source
	assert 'page.locator(".home-intelligence-card")' in source
	assert "page.goBack" in source
	assert "page.goForward" in source
	assert '[aria-label="Working branch"]' in source


def test_business_hub_legacy_contract_now_follows_phase5_indices():
	source = HUB_TEST.read_text(encoding="utf-8")
	assert "homeSnapshot.indices" in source
	assert "[\'stock\', \'banking\', \'branch\', \'cash_shift\']" not in source
	for key in ("sales", "cash", "stock", "expenses", "receivables", "payables", "branch", "banking"):
		assert key in source
