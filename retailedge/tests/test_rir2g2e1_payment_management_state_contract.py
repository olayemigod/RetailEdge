from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "public" / "js" / "payment_management" / "PaymentManagement.vue"


def _source() -> str:
	return PAGE.read_text(encoding="utf-8")


def test_payment_management_requires_shared_state_components():
	source = _source()
	for component in ("EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState"):
		assert component in source
	assert 'const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeLinkField", "EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState"];' in source


def test_metadata_state_is_explicit_and_retryable():
	source = _source()
	assert 'v-if="metadataLoading"' in source
	assert 'v-else-if="metadataError"' in source
	assert '@retry="loadMetadata"' in source
	assert "metadataLoading: true" in source
	assert 'metadataError: ""' in source
	assert "this.metadataLoading = true;" in source
	assert "this.metadataLoading = false;" in source


def test_draft_list_load_state_is_separate_from_action_feedback():
	source = _source()
	assert 'v-else-if="draftLoadError"' in source
	assert '@retry="loadDraftPayments"' in source
	assert 'v-else-if="draftLoading"' in source
	assert 'v-else-if="!draftPayments.length"' in source
	assert 'v-if="draftError" class="payment-error compact"' in source
	assert 'draftLoadError: ""' in source
	assert 'draftError: ""' in source
	assert 'this.draftLoadError = errorMessage(error, "Draft customer payments failed to load.");' in source


def test_settlement_load_failure_is_separate_from_action_feedback():
	source = _source()
	assert 'v-if="settlement.loadError"' in source
	assert '@retry="loadSettlementInvoice(settlement.invoice)"' in source
	assert 'v-else-if="settlement.loading"' in source
	assert 'v-if="settlement.actionError" class="payment-error"' in source
	assert 'loadError: ""' in source
	assert 'actionError: ""' in source
	assert "settlement.error" not in source
	assert 'this.settlement.loadError = errorMessage(error, "Sales Invoice settlement context failed to load.");' in source
	assert 'this.settlement.actionError = __("Selected advance allocations cannot exceed the current invoice outstanding amount.");' in source


def test_primary_empty_states_use_shared_component():
	source = _source()
	assert 'title="No draft payments awaiting submission"' in source
	assert 'title="No eligible customer advances"' in source
	assert 'title="No unapplied customer advances"' in source
	assert 'v-else-if="!advances.length"' in source


def test_customer_advance_load_state_uses_shared_components():
	source = _source()
	assert 'v-if="advanceLoadError"' in source
	assert '@retry="loadAdvances"' in source
	assert 'v-else-if="loading"' in source
	assert 'advanceLoadError: ""' in source
	assert 'this.advanceLoadError = errorMessage(error, "Customer advances failed to load.");' in source


def test_legacy_primary_text_state_blocks_are_removed():
	source = _source()
	assert 'v-else-if="draftLoading" class="payment-state compact"' not in source
	assert 'v-else-if="loading" class="payment-state"' not in source
	assert 'v-if="error" class="payment-error"' not in source
	assert "this.error" not in source


def test_customer_advance_bank_reference_is_validated_before_create_and_errors_are_friendly():
	source = _source()
	assert "syncAdvanceReferenceRequirement" in source
	assert 'dialog.set_df_property("reference_no", "reqd", required ? 1 : 0)' in source
	assert 'dialog.set_df_property("reference_date", "reqd", required ? 1 : 0)' in source
	assert 'title: __("Reference No required")' in source
	assert "Enter the bank transaction or transfer reference before creating this advance." in source
	assert "window.retailedge?.userErrorMessage?.(error, fallback)" in source
	assert "error?.exc || error?.exception" not in source
	assert "retailedge.stock_movement_filters.branch_query" in source


def test_successful_customer_advance_is_not_reclassified_as_create_failure_by_refresh():
	source = _source()
	create_start = source.index("let result = null;")
	success_start = source.index("dialog.hide();", create_start)
	create_segment = source[create_start:success_start]
	assert "create_customer_advance_draft" in create_segment
	assert "loadAdvances" not in create_segment
	assert "loadDraftPayments" not in create_segment
	post_create = source[success_start:source.index("openPaymentHistory()", success_start)]
	assert "Customer advance draft created. Review it before submission." in post_create
	assert post_create.index("Customer advance draft created. Review it before submission.") < post_create.index("await this.loadAdvances();")
	assert post_create.index("await this.loadAdvances();") < post_create.index("await this.loadDraftPayments();")
