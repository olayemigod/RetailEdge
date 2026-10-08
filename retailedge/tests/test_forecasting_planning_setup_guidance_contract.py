from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLANNING = ROOT / "public/js/forecasting_planning/ForecastingPlanning.vue"


def _source() -> str:
	return PLANNING.read_text(encoding="utf-8")


def test_branch_accounting_warning_describes_current_truth_without_false_setup_promise():
	source = _source()
	assert "Branch-level accounting forecasts are not available in the current planning model" in source
	assert "posted accounting entries do not yet have a verified Branch accounting basis" in source
	assert "If your role permits Company-wide access, clear Branch above and Apply Plan" in source
	assert "complete Branch accounting setup" not in source


def test_budget_unavailability_is_kept_out_of_generic_warning_cards():
	source = _source()
	assert '.filter(([key, d]) => key !== "budget" && d && d.available === false)' in source
	assert "Budget comparison unavailable" in source
	assert "missing budget comparison does not block the rest of the forecast" in source
	assert "Budget comparison is optional and does not block the rest of Forecasting & Planning" in source


def test_budget_remediation_uses_only_existing_permission_aware_destinations():
	source = _source()
	assert 'item.target_type === "Page" && item.target === "retailedge-setup"' in source
	assert 'reason.includes("expense categories") && this.canOpenBusinessSetup' in source
	assert 'reason.includes("submitted budget") || reason.includes("budget matches")' in source
	assert '&& this.canUseNativeDesk' in source
	assert 'window.open("/app/budget", "_blank", "noopener,noreferrer")' in source


def test_planning_setup_guidance_preserves_accounting_and_scenario_boundaries():
	source = _source()
	assert "Forecast and Plan are analytical only and do not create transactions." in source
	assert ':disabled="!filters.company || !canCreateScenario || !canUseNativeDesk"' in source
	assert "window.EdgeSuiteUI?.openCreateSurface" in source
	assert "customerFacingCopy(d.reason" in source
	assert "customerFacingCopy(meta.reason" in source
