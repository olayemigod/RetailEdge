from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import bank_exception_summary as summary


def test_bank_exception_summary_classifies_existing_match_state_without_candidate_discovery(monkeypatch):
	frappe.session.user = "Administrator"
	monkeypatch.setattr(frappe, "has_permission", lambda *args, **kwargs: True)
	rows = [
		frappe._dict(
			name="M1",
			transaction_date="2026-08-01",
			bank_amount=100,
			decision_status="Suggested",
			execution_status="Not Executed",
		),
		frappe._dict(
			name="M2",
			transaction_date="2026-08-02",
			bank_amount=200,
			decision_status="Confirmed",
			execution_status="Not Executed",
		),
		frappe._dict(
			name="M3",
			transaction_date="2026-08-03",
			bank_amount=300,
			decision_status="Confirmed",
			execution_status="Blocked",
		),
		frappe._dict(
			name="M4",
			transaction_date="2026-08-04",
			bank_amount=400,
			decision_status="Confirmed",
			execution_status="Failed",
		),
	]
	with (
		patch(
			"retailedge.bank_exception_summary.validate_report_scope",
			return_value={"restricted": False, "allowed_branches": [], "branch": ""},
		),
		patch("retailedge.bank_exception_summary.frappe.get_list", return_value=rows),
	):
		result = summary.get_bank_exception_summary(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-20"}
		)
	cards = {row["label"]: row["value"] for row in result["summary"]}
	assert cards["Bank Matches Need Review"] == 1
	assert cards["Ready for Reconciliation"] == 1
	assert cards["Reconciliation Exceptions"] == 2
	assert result["metadata"]["candidate_discovery"] is False


def test_bank_exception_summary_uses_bounded_permission_aware_get_list(monkeypatch):
	frappe.session.user = "Administrator"
	monkeypatch.setattr(frappe, "has_permission", lambda *args, **kwargs: True)
	with (
		patch(
			"retailedge.bank_exception_summary.validate_report_scope",
			return_value={"restricted": True, "allowed_branches": ["HQ"], "branch": "HQ"},
		),
		patch("retailedge.bank_exception_summary.frappe.get_list", return_value=[]) as get_list,
	):
		summary.get_bank_exception_summary(
			{"company": "Test Company", "branch": "HQ", "from_date": "2026-08-01", "to_date": "2026-08-20"}
		)
	kwargs = get_list.call_args.kwargs
	assert kwargs["limit"] == summary.MAX_BANK_MATCH_SUMMARY_ROWS + 1
	assert kwargs["filters"]["company"] == "Test Company"
	assert kwargs["filters"]["branch"] == "HQ"


def test_bank_exception_summary_source_does_not_use_candidate_discovery_or_mutation():
	source = Path(summary.__file__).read_text(encoding="utf-8")
	for forbidden in (
		"find_payment_entry_candidates_for_bank_transaction",
		"find_sales_invoice_candidates_for_bank_transaction",
		"ignore_permissions=True",
		"frappe.db.commit(",
		".submit(",
	):
		assert forbidden not in source
