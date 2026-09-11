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
	assert "this.settlement.actionError = __("Selected advance allocations cannot exceed the current invoice outstanding amount.");" in source


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
