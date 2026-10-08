from __future__ import annotations

import inspect
from unittest.mock import patch

import frappe

from retailedge import supplier_payables
from retailedge import supplier_payables_branch_fallback as fallback


def _filters(**overrides):
	values = {
		"company": "Scope Co",
		"as_of_date": "2026-10-08",
		"branch": "Branch A",
		"supplier": "",
		"supplier_group": "",
		"status": "",
		"ageing_bucket": "All",
		"overdue_only": 0,
	}
	values.update(overrides)
	return frappe._dict(values)


def _candidate(name="PINV-LEGACY", outstanding=1250.0):
	return frappe._dict(
		name=name,
		posting_date="2026-09-01",
		due_date="2026-09-30",
		supplier="SUP-1",
		supplier_name="Alpha Supply",
		currency="NGN",
		conversion_rate=1.0,
		outstanding_amount=outstanding,
		status="Unpaid",
		is_return=0,
		retailedge_branch="",
	)


def _empty_dataset():
	return {
		"title": "Supplier Payables",
		"columns": [],
		"rows": [],
		"summary": [],
		"company_currency": "NGN",
		"scan": {"invoices": 0, "invoice_limit": 2000},
	}


def test_branch_scoped_payables_recovers_blank_historical_invoice_read_only():
	candidate = _candidate()
	with (
		patch.object(
			fallback.purchase_reporting,
			"_invoice_branch_scope",
			return_value=("retailedge_branch", "Branch A"),
		),
		patch.object(fallback.purchase_reporting, "_outstanding_is_company_currency", return_value=True),
		patch.object(fallback.frappe, "get_list", return_value=[candidate]) as get_list,
		patch.object(fallback, "_resolve_legacy_branch", return_value="Branch A") as resolve,
	):
		result = fallback.merge_legacy_branch_payables(_empty_dataset(), _filters())

	assert [row["invoice"] for row in result["rows"]] == ["PINV-LEGACY"]
	assert result["rows"][0]["branch"] == "Branch A"
	assert result["rows"][0]["outstanding"] == 1250.0
	assert result["summary"][0]["value"] == 1250.0
	assert result["summary"][1]["value"] == 1
	assert result["scan"]["legacy_branch_rows_added"] == 1
	assert result["scan"]["invoices"] == 1
	resolve.assert_called_once_with("PINV-LEGACY")

	call = get_list.call_args
	assert call.args[0] == "Purchase Invoice"
	assert call.kwargs["filters"]["docstatus"] == 1
	assert call.kwargs["filters"]["company"] == "Scope Co"
	assert call.kwargs["filters"]["posting_date"] == ["<=", "2026-10-08"]
	assert call.kwargs["filters"]["outstanding_amount"] == [">", 0]
	assert ["retailedge_branch", "is", "not set"] in call.kwargs["or_filters"]
	assert ["retailedge_branch", "=", ""] in call.kwargs["or_filters"]


def test_resolved_legacy_invoice_outside_authorized_branch_fails_closed_without_scope_counts():
	with (
		patch.object(
			fallback.purchase_reporting,
			"_invoice_branch_scope",
			return_value=("retailedge_branch", "Branch A"),
		),
		patch.object(fallback.frappe, "get_list", return_value=[_candidate()]),
		patch.object(fallback, "_resolve_legacy_branch", return_value="Branch B"),
	):
		result = fallback.merge_legacy_branch_payables(_empty_dataset(), _filters())

	assert result["rows"] == []
	assert result["scan"]["legacy_branch_rows_added"] == 0
	assert result["scan"]["invoices"] == 0
	for forbidden_key in (
		"legacy_branch_candidates",
		"legacy_branch_resolved",
		"legacy_branch_unresolved",
		"legacy_branch_in_scope",
	):
		assert forbidden_key not in result["scan"]


def test_ambiguous_legacy_invoice_is_not_exposed():
	with (
		patch.object(
			fallback.purchase_reporting,
			"_invoice_branch_scope",
			return_value=("retailedge_branch", ["in", ["Branch A", "Branch B"]]),
		),
		patch.object(fallback.frappe, "get_list", return_value=[_candidate()]),
		patch.object(fallback, "_resolve_legacy_branch", return_value=""),
	):
		result = fallback.merge_legacy_branch_payables(_empty_dataset(), _filters(branch=""))

	assert result["rows"] == []
	assert result["scan"]["legacy_branch_rows_added"] == 0
	assert result["scan"]["invoices"] == 0


def test_unscoped_company_view_keeps_standard_dataset_without_extra_scan():
	dataset = _empty_dataset()
	with (
		patch.object(
			fallback.purchase_reporting,
			"_invoice_branch_scope",
			return_value=("retailedge_branch", None),
		),
		patch.object(fallback.frappe, "get_list") as get_list,
	):
		result = fallback.merge_legacy_branch_payables(dataset, _filters(branch=""))

	assert result is dataset
	get_list.assert_not_called()


def test_supplier_payables_wrapper_preserves_existing_engine_and_current_balance_contract():
	source = inspect.getsource(supplier_payables)
	assert "purchase_reporting._build_supplier_payables_dataset(filters)" in source
	assert "merge_legacy_branch_payables(dataset, filters)" in source
	assert source.count("dataset = _build_current_dataset(resolved)") == 2
	assert '"balance_basis": "current_outstanding"' in source
	assert '"historical_balance_supported": False' in source


def test_legacy_branch_fallback_never_mutates_purchase_invoices_or_exposes_cross_scope_counts():
	source = inspect.getsource(fallback)
	for forbidden in (
		".save(",
		".submit(",
		".cancel(",
		"frappe.db.set_value(",
		"frappe.db.commit(",
		"ignore_permissions=True",
		'"legacy_branch_candidates"',
		'"legacy_branch_resolved"',
		'"legacy_branch_unresolved"',
		'"legacy_branch_in_scope"',
	):
		assert forbidden not in source
	assert "resolve_transaction_branch(doc)" in source
	assert 'frappe.has_permission("Purchase Invoice", "read", doc=doc)' in source
