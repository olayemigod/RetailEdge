from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_360 = ROOT / "public/js/customer_360/Customer360.vue"
PROJECT_OPERATIONS = ROOT / "public/js/project_operations/ProjectOperations.vue"
FORECASTING = ROOT / "public/js/forecasting_planning/ForecastingPlanning.vue"


def _source(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_all_g2e2_pages_require_shared_state_components():
	for path in (CUSTOMER_360, PROJECT_OPERATIONS, FORECASTING):
		source = _source(path)
		for component in ("EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState"):
			assert component in source, path


def test_customer_360_separates_metadata_and_data_state_ownership():
	source = _source(CUSTOMER_360)
	assert 'metadataLoading: true' in source
	assert 'metadataError: ""' in source
	assert 'dataError: ""' in source
	assert 'v-if="metadataError"' in source
	assert '@retry="fetchMetadata"' in source
	assert 'v-else-if="dataError"' in source
	assert '@retry="fetchData"' in source
	assert 'v-else-if="!filters.customer"' in source
	assert 'title="Select a customer"' in source
	assert '<div v-else-if="loading" class="customer-360-loading">' not in source
	assert '<div v-if="error" class="alert alert-danger customer-360-error">' not in source


def test_customer_360_preserves_company_branch_customer_cascade():
	source = _source(CUSTOMER_360)
	assert 'onCompanySelected(option)' in source
	assert 'this.filters.branch = ""; this.clearCustomer();' in source
	assert 'onBranchSelected(option)' in source
	assert 'clearBranch()' in source
	assert 'clearCustomer()' in source


def test_project_operations_separates_navigation_and_context_failures():
	source = _source(PROJECT_OPERATIONS)
	assert 'navigationLoading: true' in source
	assert 'navigationError: ""' in source
	assert 'contextError: ""' in source
	assert 'v-if="navigationError"' in source
	assert '@retry="loadNavigation"' in source
	assert 'v-else-if="contextError"' in source
	assert '@retry="loadContext"' in source
	assert 'v-else-if="!project"' in source
	assert 'title="Select a project"' in source
	assert 'class="project-error"' not in source


def test_project_context_owner_and_business_calls_are_preserved():
	source = _source(PROJECT_OPERATIONS)
	for contract in (
		"retailedge.project_operations.get_project_funds_context",
		"retailedge.project_activity.get_project_activity_context",
		"retailedge.project_budget.get_project_budget_context",
	):
		assert contract in source
	assert "Promise.all" in source
	assert "get_project_funds_context" in source


def test_forecasting_primary_states_are_mutually_exclusive_and_retryable():
	source = _source(FORECASTING)
	assert 'metadataError: ""' in source
	assert 'dataError: ""' in source
	assert 'v-if="metadataError"' in source
	assert '@retry="bootstrap"' in source
	assert 'v-else-if="metadataLoading"' in source
	assert 'v-else-if="dataError"' in source
	assert '@retry="fetchData"' in source
	assert 'v-else-if="loading"' in source
	assert 'v-else-if="!filters.company"' in source
	assert 'title="Select a company"' in source
	assert '<template v-else>' in source
	assert '<div v-if="error" class="alert error">' not in source


def test_forecasting_scenario_performance_uses_shared_state_contract():
	source = _source(FORECASTING)
	assert 'v-if="performanceLoading"' in source
	assert 'message="Loading scenario performance…"' in source
	assert 'v-else-if="performanceError"' in source
	assert '@retry="fetchPerformance"' in source
	assert 'v-else-if="!performanceRows.length"' in source
	assert 'title="No completed scenario periods"' in source


def test_g2e2_does_not_reclassify_contextual_domain_empty_reasons():
	source = _source(FORECASTING)
	for contract in (
		"cashCommitmentReason",
		"budgetReason",
		"inventoryReason",
		"No known due commitments fall inside this forecast horizon.",
		"No observed inventory demand is available for this scope.",
	):
		assert contract in source
