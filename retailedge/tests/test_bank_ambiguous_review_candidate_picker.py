from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.bank_transaction_match_workflow import (
	get_ambiguous_payment_entry_review_candidates,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_JS = (
	ROOT
	/ "retailedge/report/retailedge_bank_transaction_matching/retailedge_bank_transaction_matching.js"
)


def _candidate(name, payment_type, party=None):
	return {
		"document_type": "Payment Entry",
		"document_name": name,
		"suggested_document": name,
		"posting_date": "2026-10-01",
		"party": party,
		"party_type": "Customer" if party else None,
		"customer": party,
		"customer_display": party,
		"candidate_amount": 200000,
		"amount_difference": 0,
		"amount_scenario": "Submitted Payment Entry Amount",
		"candidate_category": "payment_entry_match",
		"candidate_category_label": "Payment Entry Match",
		"payment_event_found": 1,
		"payment_event_source": "Payment Entry",
		"payment_entry_paid_amount": 200000,
		"payment_entry_allocated_amount": 200000 if party else 0,
		"payment_entry_payment_type": payment_type,
		"payment_account": "Bank - RC",
		"reference": party or "Cash Deposit",
		"branch": "Ketu",
		"score": 75,
		"confidence": "Possible Match",
		"reason": "Competing submitted Payment Entry.",
		"reference_match_exact": 0,
		"reference_match_strength": "none",
		"date_difference_days": 0,
		"date_exact": 1,
		"date_in_normal_window": 1,
		"account_match": 1,
		"account_match_available": 1,
		"identity_ambiguous": 1,
		"identity_competing_candidates": 2,
		"identity_review_reason": "Two submitted Payment Entries require human selection.",
	}


@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
@patch(
	"retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings",
	return_value={},
)
@patch("retailedge.bank_transaction_match_workflow.find_payment_entry_candidates_for_bank_transaction")
@patch("retailedge.bank_transaction_match_workflow.normalize_bank_transaction")
def test_review_candidates_return_both_competing_payment_entries_without_mutation(
	normalize_bank_transaction,
	find_candidates,
	_settings,
	_access,
	_manage,
):
	normalize_bank_transaction.return_value = frappe._dict(
		bank_transaction="ACC-BTN-2026-00020",
		transaction_date="2026-10-01",
		bank_account="Access Bank Ketu - Access Bank",
		amount=200000,
		direction="Inflow",
	)
	find_candidates.return_value = [
		_candidate("ACC-PAY-2026-00016", "Internal Transfer"),
		_candidate("ACC-PAY-2026-00018", "Receive", party="Mathew Alao"),
	]

	rows = get_ambiguous_payment_entry_review_candidates(
		"ACC-BTN-2026-00020",
		filters={"company": "RetailEdge Consulting"},
		limit=20,
	)

	assert [row["suggested_document"] for row in rows] == [
		"ACC-PAY-2026-00016",
		"ACC-PAY-2026-00018",
	]
	assert all(row["action_status"] == "Needs Review" for row in rows)
	assert all(row["eligible_for_auto_prepare"] == 0 for row in rows)
	assert all(row["eligible_for_auto_confirm"] == 0 for row in rows)
	assert rows[0]["payment_entry_payment_type"] == "Internal Transfer"
	assert rows[0]["party_type"] is None
	assert rows[1]["party_type"] == "Customer"
	assert rows[0]["review_candidate_key"] == "Payment Entry|ACC-PAY-2026-00016"


@patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value")
@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
@patch(
	"retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings",
	return_value={},
)
@patch("retailedge.bank_transaction_match_workflow.find_payment_entry_candidates_for_bank_transaction")
@patch("retailedge.bank_transaction_match_workflow.normalize_bank_transaction")
def test_confirmed_candidate_for_same_bank_transaction_remains_selectable(
	normalize_bank_transaction,
	find_candidates,
	_settings,
	_access,
	_manage,
	get_value,
):
	normalize_bank_transaction.return_value = frappe._dict(
		bank_transaction="ACC-BTN-2026-00020",
		transaction_date="2026-10-01",
		bank_account="Access Bank Ketu - Access Bank",
		amount=200000,
		direction="Inflow",
	)
	confirmed = _candidate("ACC-PAY-2026-00016", "Internal Transfer")
	confirmed["decision_status"] = "Confirmed"
	confirmed["match_record"] = "RE-BTM-0001"
	find_candidates.return_value = [
		confirmed,
		_candidate("ACC-PAY-2026-00018", "Receive", party="Mathew Alao"),
	]
	get_value.return_value = "ACC-BTN-2026-00020"

	rows = get_ambiguous_payment_entry_review_candidates("ACC-BTN-2026-00020")

	assert [row["suggested_document"] for row in rows] == [
		"ACC-PAY-2026-00016",
		"ACC-PAY-2026-00018",
	]


@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
@patch(
	"retailedge.bank_transaction_match_workflow.get_bank_transaction_matching_settings",
	return_value={},
)
@patch("retailedge.bank_transaction_match_workflow.find_payment_entry_candidates_for_bank_transaction")
@patch("retailedge.bank_transaction_match_workflow.normalize_bank_transaction")
def test_picker_expands_to_full_reported_competing_set(
	normalize_bank_transaction,
	find_candidates,
	_settings,
	_access,
	_manage,
):
	normalize_bank_transaction.return_value = frappe._dict(
		bank_transaction="ACC-BTN-MANY",
		transaction_date="2026-10-01",
		bank_account="Access Bank Ketu - Access Bank",
		amount=200000,
		direction="Inflow",
	)
	first_page = []
	for index in range(20):
		candidate = _candidate(f"ACC-PAY-{index:03d}", "Receive", party=f"Customer {index}")
		candidate["identity_competing_candidates"] = 21
		first_page.append(candidate)
	full_set = list(first_page)
	extra = _candidate("ACC-PAY-020", "Receive", party="Customer 20")
	extra["identity_competing_candidates"] = 21
	full_set.append(extra)
	find_candidates.side_effect = [first_page, full_set]

	rows = get_ambiguous_payment_entry_review_candidates(
		"ACC-BTN-MANY",
		limit=20,
	)

	assert len(rows) == 21
	assert find_candidates.call_count == 2
	assert find_candidates.call_args_list[0].kwargs["limit"] == 20
	assert find_candidates.call_args_list[1].kwargs["limit"] == 21


def test_review_dialog_requires_explicit_choice_for_ambiguous_candidates():
	source = REPORT_JS.read_text(encoding="utf-8")
	assert 'fieldname: "candidate_choices"' in source
	assert "load_ambiguous_review_candidates(dialog, args);" in source
	assert 'method: "retailedge.api.get_ambiguous_payment_entry_review_candidates"' in source
	assert "function ensure_explicit_ambiguous_candidate_selection(args)" in source
	assert "if (args._explicit_candidate_selected) return true;" in source
	assert "args._explicit_candidate_selected = false;" in source
	assert "args._explicit_candidate_selected = true;" in source
	assert "if (!ensure_explicit_ambiguous_candidate_selection(args)) return;" in source


def test_review_candidate_switch_clears_old_review_record_identity():
	source = REPORT_JS.read_text(encoding="utf-8")
	assert "if (previousDocument && previousDocument !== args.suggested_document)" in source
	assert "args.match_record = null;" in source
	assert "args.match_decision = null;" in source
