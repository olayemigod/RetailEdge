from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_JS = ROOT / "public/js/bank_matching_edgesuite_workspace.js"


def test_bank_workspace_discards_stale_refresh_responses():
	source = WORKSPACE_JS.read_text(encoding="utf-8")

	assert "let refreshRequestId = 0;" in source
	assert "const requestId = ++refreshRequestId;" in source
	assert "const requestArgs = {" in source
	assert "if (requestId !== refreshRequestId) return;" in source
	assert "if (requestId === refreshRequestId) state.loading = false;" in source


def test_bank_workspace_keeps_existing_rows_visible_while_refreshing():
	source = WORKSPACE_JS.read_text(encoding="utf-8")

	assert "state.loading && !state.rows.length" in source
	assert "state.error && !state.rows.length" in source
	assert "state.rows.length ? renderTable() : null" in source


def test_stale_active_review_is_not_labelled_as_historical():
	source = WORKSPACE_JS.read_text(encoding="utf-8")

	assert "const historicalReadOnly = Boolean(" in source
	assert "const staleActiveReview = Boolean(" in source
	assert "Stored suggestion needs replacement — displayed read-only until a valid candidate is selected." in source
	assert "Candidate Needs Replacement" in source
	assert "Historical review snapshot — displayed read-only." in source


def test_stale_review_can_find_and_switch_replacement_candidate():
	source = WORKSPACE_JS.read_text(encoding="utf-8")

	assert "existingMatchName" in source
	assert "async function findReplacementForReview()" in source
	assert "await findCandidates(bankTransaction, matchName);" in source
	assert 'method: "retailedge.api.switch_bank_transaction_match_candidate"' in source
	assert 'rawCandidates.filter((row) => row.document_type === "Payment Entry")' in source
	assert "Use Selected Candidate" in source
	assert "Find Replacement" in source
	assert "await showReviewMatchDialog(result.match_name, row);" in source
	assert "await refresh();" in source


def test_review_modal_remounts_on_each_open_to_reset_scroll_position():
	source = WORKSPACE_JS.read_text(encoding="utf-8")

	assert "instanceKey: 0" in source
	assert "state.review.instanceKey += 1;" in source
	review_modal_index = source.index("function renderReviewModal()")
	modal_key_index = source.index("key: state.review.instanceKey", review_modal_index)
	assert modal_key_index > review_modal_index


def test_historical_reconciled_review_does_not_offer_replacement():
	source = WORKSPACE_JS.read_text(encoding="utf-8")

	footer_index = source.index("const buttons = [actionButton(t(\"Close\")")
	stale_index = source.index("if (staleActiveReview)", footer_index)
	decide_index = source.index("else if (canDecide)", stale_index)

	assert footer_index < stale_index < decide_index
	assert "historicalReadOnly" in source
