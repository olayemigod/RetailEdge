from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import planning_scope

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "public/js/forecasting_planning/ForecastingPlanning.vue"
API = ROOT / "planning_scenario_api.py"


def test_planning_scope_delegates_to_operational_branch_contract():
	source = inspect.getsource(planning_scope)
	assert "resolve_operational_branch" in source
	assert "get_user_allowed_branches" not in source
	assert "user_has_global_branch_access" not in source
	assert "validate_user_branch_access" not in source


def test_planning_scenario_api_is_permission_aware_bounded_and_scope_aware():
	source = API.read_text(encoding="utf-8")
	assert "MAX_SCENARIO_RESULTS = 20" in source
	assert "get_operational_branch_scope" in source
	assert "resolve_planning_branch_scope" in source
	assert "frappe.get_list(" in source
	assert "frappe.has_permission" in source
	assert "frappe.get_all" not in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit" not in source


def test_scenario_load_returns_only_page_fields_and_hides_snapshot_payload():
	source = API.read_text(encoding="utf-8")
	assert "SCENARIO_PAGE_FIELDS" in source
	assert '"forecast_snapshot_json"' not in source
	assert "resolve_planning_branch_scope" in source


def test_forecasting_page_uses_governed_scenario_search_and_load_api():
	source = PAGE.read_text(encoding="utf-8")
	assert "retailedge.planning_scenario_api.search_planning_scenarios" in source
	assert "retailedge.planning_scenario_api.get_planning_scenario" in source
	assert 'call("frappe.client.get_list"' not in source
	assert 'call("frappe.client.get"' not in source
	assert "company: this.filters.company" in source
	assert "branch: this.filters.branch" in source
