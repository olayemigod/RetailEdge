from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.reconciliation_approval import build_live_reconciliation_approval_state


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_JS = ROOT / "public/js/bank_matching_edgesuite_workspace.js"


def _review_doc(**overrides):
	values = {
		"name": "RE-BTM-2026-0142",
		"bank_transaction": "ACC-BTN-2026-00018",
		"decision_status": "Confirmed",
		"execution_status": "",
		"approval_status": "Pending",
		"confirmed_by": "accounts@example.com",
		"confirmed_on": "2026-08-24 10:00:00",
		"approved_by": None,
		"approved_on": None,
		"approval_candidate_identity": "",
		"bank_amount": 620000,
		"candidate_amount": 620000,
		"suggested_document_type": "Payment Entry",
		"suggested_document": "ACC-PAY-2026-00010",
		"payment_account": "GT Bank - RC",
		"resolved_payment_account": "GT Bank - RC",
	}
	values.update(overrides)
	return SimpleNamespace(**values)


@patch("retailedge.reconciliation_approval.build_reconciliation_approval_state")
@patch("retailedge.reconciliation_approval._refresh_match_candidate_context")
@patch("retailedge.reconciliation_approval.frappe.get_doc")
def test_reconciled_historical_review_does_not_revalidate_candidate(
	get_doc,
	refresh_candidate,
	build_state,
):
	doc = _review_doc(execution_status="Executed")
	get_doc.return_value = doc
	build_state.return_value = {
		"status": "Approved",
		"is_satisfied": True,
		"can_approve": False,
	}

	state = build_live_reconciliation_approval_state(doc.name)

	refresh_candidate.assert_not_called()
	assert state["read_only"] is True
	assert state["read_only_history"] is True
	assert state["live_validation_ok"] is None
	assert state["status"] == "Approved"


@patch("retailedge.reconciliation_approval.build_reconciliation_approval_state")
@patch(
	"retailedge.reconciliation_approval._refresh_match_candidate_context",
	side_effect=frappe.ValidationError(
		"Locked candidate no longer validates against current accounting data; no alternate candidate was selected."
	),
)
@patch(
	"retailedge.reconciliation_approval.frappe.db.get_value",
	return_value="Unreconciled",
)
@patch("retailedge.reconciliation_approval.frappe.db.exists", return_value=True)
@patch("retailedge.reconciliation_approval.frappe.get_doc")
def test_stale_active_review_returns_read_only_state_instead_of_throwing(
	get_doc,
	_exists,
	_get_value,
	_refresh_candidate,
	build_state,
):
	doc = _review_doc()
	get_doc.return_value = doc
	build_state.return_value = {
		"status": "Pending",
		"is_satisfied": False,
		"can_approve": True,
	}

	state = build_live_reconciliation_approval_state(doc.name)

	assert state["read_only"] is True
	assert state["read_only_history"] is False
	assert state["live_validation_ok"] is False
	assert state["can_approve"] is False
	assert state["is_satisfied"] is False
	assert state["status"] == "Invalidated"
	assert "stored review remains available read-only" in state["reason"].lower()
	assert "replacement candidate" in state["reason"].lower()


def test_stale_display_validation_restores_frappe_message_log():
	doc = _review_doc()
	local = SimpleNamespace(message_log=[{"message": "keep me"}])

	def stale_validator(_doc):
		local.message_log.append(
			{
				"message": (
					"Locked candidate no longer validates against current accounting data; "
					"no alternate candidate was selected."
				)
			}
		)
		raise frappe.ValidationError("stale candidate")

	with (
		patch("retailedge.reconciliation_approval.frappe.local", local),
		patch("retailedge.reconciliation_approval.frappe.get_doc", return_value=doc),
		patch("retailedge.reconciliation_approval.frappe.db.exists", return_value=True),
		patch("retailedge.reconciliation_approval.frappe.db.get_value", return_value="Unreconciled"),
		patch(
			"retailedge.reconciliation_approval._refresh_match_candidate_context",
			side_effect=stale_validator,
		),
		patch(
			"retailedge.reconciliation_approval.build_reconciliation_approval_state",
			return_value={
				"status": "Pending",
				"is_satisfied": False,
				"can_approve": True,
			},
		),
	):
		state = build_live_reconciliation_approval_state(doc.name)

	assert state["live_validation_ok"] is False
	assert local.message_log == [{"message": "keep me"}]


@patch("retailedge.reconciliation_approval.build_reconciliation_approval_state")
@patch("retailedge.reconciliation_approval._refresh_match_candidate_context")
@patch(
	"retailedge.reconciliation_approval.frappe.db.get_value",
	return_value="Unreconciled",
)
@patch("retailedge.reconciliation_approval.frappe.db.exists", return_value=True)
@patch("retailedge.reconciliation_approval.frappe.get_doc")
def test_active_valid_review_keeps_live_approval_behavior(
	get_doc,
	_exists,
	_get_value,
	refresh_candidate,
	build_state,
):
	doc = _review_doc(decision_status="Needs Review")
	get_doc.return_value = doc
	build_state.return_value = {
		"status": "Pending",
		"is_satisfied": False,
		"can_approve": False,
	}

	state = build_live_reconciliation_approval_state(doc.name)

	refresh_candidate.assert_called_once_with(doc)
	assert state["read_only"] is False
	assert state["read_only_history"] is False
	assert state["live_validation_ok"] is True


def test_edgesuite_review_hydration_is_partial_failure_tolerant():
	source = WORKSPACE_JS.read_text(encoding="utf-8")

	assert "const doc = await getMatchDocument(matchName);" in source
	assert "Promise.allSettled([" in source
	assert "historicalEvidenceFallback(doc, candidateSnapshot)" in source
	assert "historicalApprovalFallback(" in source
	assert "const approvalIsReadOnly = Boolean(" in source
	assert "if (approvalIsReadOnly)" in source
	assert "approval.live_validation_ok === false" in source
	assert "const reviewReadOnly = Boolean(" in source
	assert "Historical review snapshot — displayed read-only." in source
	assert "state.review.warning" in source


def test_historical_review_actions_are_hidden_when_read_only():
	source = WORKSPACE_JS.read_text(encoding="utf-8")

	assert "const canDecide =" in source
	assert "!reviewReadOnly &&" in source
	assert "const canApprove = !reviewReadOnly && Boolean(approval.can_approve);" in source
	assert "const canRequestApproval =" in source


def test_historical_read_only_review_prefers_stored_snapshot_over_live_evidence():
	source = WORKSPACE_JS.read_text(encoding="utf-8")
	read_only_index = source.index("const approvalIsReadOnly = Boolean(")
	historical_index = source.index(
		"state.review.evidence = historicalEvidenceFallback(doc, candidateSnapshot);",
		read_only_index,
	)
	live_index = source.index(
		"evidenceResult.value || historicalEvidenceFallback(doc, candidateSnapshot)",
		read_only_index,
	)

	assert historical_index > read_only_index
	assert live_index > historical_index
