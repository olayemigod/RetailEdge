from __future__ import annotations

import inspect
from unittest.mock import patch

import frappe

from retailedge import supplier_payables


def _filters(**overrides):
	values = {
		"company": "Scope Co",
		"as_of_date": "2026-10-08",
		"branch": "Branch A",
		"supplier": "",
		"supplier_group": "",
		"status": "",
	}
	values.update(overrides)
	return frappe._dict(values)


def test_branch_scoped_payables_scan_current_open_bills_and_blank_legacy_candidates():
	rows = [
		frappe._dict(name="PINV-STORED", retailedge_branch="Branch A"),
		frappe._dict(name="PINV-LEGACY", retailedge_branch=""),
		frappe._dict(name="PINV-OTHER", retailedge_branch="Branch B"),
	]
	with (
		patch.object(
			supplier_payables.purchase_reporting,
			"_invoice_branch_scope",
			return_value=("retailedge_branch", "Branch A"),
		),
		patch.object(supplier_payables.frappe, "get_list", return_value=rows) as get_list,
		patch.object(supplier_payables, "_resolve_blank_invoice_branch", return_value="Branch A") as resolve,
	):
		result, scan = supplier_payables._get_current_open_invoice_headers(_filters())

	assert [row.name for row in result] == ["PINV-STORED", "PINV-LEGACY"]
	assert result[1].branch == "Branch A"
	assert scan == {"legacy_branch_resolved": 1, "legacy_branch_unresolved": 0}
	resolve.assert_called_once_with("PINV-LEGACY")

	call = get_list.call_args
	assert call.args[0] == "Purchase Invoice"
	assert call.kwargs["filters"]["docstatus"] == 1
	assert call.kwargs["filters"]["company"] == "Scope Co"
	assert call.kwargs["filters"]["posting_date"] == ["<=", "2026-10-08"]
	assert call.kwargs["filters"]["outstanding_amount"] == [">", 0]
	assert call.kwargs["filters"]["is_return"] == 0
	assert ["retailedge_branch", "=", "Branch A"] in call.kwargs["or_filters"]
	assert ["retailedge_branch", "is", "not set"] in call.kwargs["or_filters"]
	assert ["retailedge_branch", "=", ""] in call.kwargs["or_filters"]


def test_ambiguous_blank_legacy_branch_fails_closed():
	rows = [frappe._dict(name="PINV-LEGACY", retailedge_branch="")]
	with (
		patch.object(
			supplier_payables.purchase_reporting,
			"_invoice_branch_scope",
			return_value=("retailedge_branch", ["in", ["Branch A", "Branch B"]]),
		),
		patch.object(supplier_payables.frappe, "get_list", return_value=rows),
		patch.object(supplier_payables, "_resolve_blank_invoice_branch", return_value=""),
	):
		result, scan = supplier_payables._get_current_open_invoice_headers(_filters(branch=""))

	assert result == []
	assert scan == {"legacy_branch_resolved": 0, "legacy_branch_unresolved": 1}


def test_branch_condition_matching_handles_single_and_multi_branch_scope():
	assert supplier_payables._branch_matches_condition("Branch A", "Branch A")
	assert not supplier_payables._branch_matches_condition("Branch B", "Branch A")
	assert supplier_payables._branch_matches_condition("Branch B", ["in", ["Branch A", "Branch B"]])
	assert not supplier_payables._branch_matches_condition("Branch C", ["in", ["Branch A", "Branch B"]])
	assert supplier_payables._branch_matches_condition("", None)
	assert not supplier_payables._branch_matches_condition("", "Branch A")


def test_legacy_branch_recovery_never_mutates_submitted_purchase_invoices():
	source = inspect.getsource(supplier_payables)
	for forbidden in (
		".save(",
		".submit(",
		".cancel(",
		"frappe.db.set_value(",
		"frappe.db.commit(",
		"ignore_permissions=True",
	):
		assert forbidden not in source
	assert "resolve_transaction_branch(doc)" in source
	assert 'frappe.has_permission("Purchase Invoice", "read", doc=doc)' in source


def test_supplier_payables_page_and_export_use_recovered_current_dataset():
	source = inspect.getsource(supplier_payables)
	assert source.count("dataset = _build_current_supplier_payables_dataset(resolved)") == 2
	assert '"balance_basis": "current_outstanding"' in source
	assert '"historical_balance_supported": False' in source
