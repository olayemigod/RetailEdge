from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from retailedge import purchase_reporting
from retailedge.supplier_payables_branch_fallback import merge_legacy_branch_payables


def _current_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	resolved = frappe._dict(filters or {})
	today = nowdate()
	requested = str(resolved.get("as_of_date") or "").strip()
	if requested and getdate(requested) != getdate(today):
		frappe.throw(
			_(
				"Supplier Payables currently shows ERPNext's current outstanding balances. "
				"Historical payables as of a past date require ledger reconstruction and are not presented by this simplified report."
			)
		)
	resolved.as_of_date = today
	return resolved


def _with_current_balance_metadata(dataset: dict[str, Any]) -> dict[str, Any]:
	return {
		**dataset,
		"balance_basis": "current_outstanding",
		"ageing_date": nowdate(),
		"historical_balance_supported": False,
	}


def _build_current_dataset(filters: frappe._dict) -> dict[str, Any]:
	dataset = purchase_reporting._build_supplier_payables_dataset(filters)
	return merge_legacy_branch_payables(dataset, filters)


@frappe.whitelist()
def get_supplier_payables(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = purchase_reporting.DEFAULT_PAGE_SIZE,
	sort: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	from retailedge.report_sorting import apply_materialized_report_sort

	resolved = _current_filters(filters)
	dataset = _build_current_dataset(resolved)
	apply_materialized_report_sort(dataset, sort, "supplier-payables")
	return _with_current_balance_metadata(
		purchase_reporting._page_response(dataset, page=page, page_size=page_size)
	)


@frappe.whitelist()
def get_supplier_payables_export(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	resolved = _current_filters(filters)
	dataset = _build_current_dataset(resolved)
	return _with_current_balance_metadata(purchase_reporting._export_response(dataset))
