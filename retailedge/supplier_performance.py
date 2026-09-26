from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from retailedge.purchase_analysis import _build_purchase_analysis_dataset
from retailedge.purchase_reporting import _coerce_filters, _page_response
from retailedge.supplier_payables import get_supplier_payables_export

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


@frappe.whitelist()
def get_supplier_performance(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
	sort: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	from retailedge.report_sorting import apply_materialized_report_sort

	resolved = _coerce_filters(filters)
	dataset = _build_supplier_performance_dataset(resolved)
	apply_materialized_report_sort(dataset, sort, "supplier-performance")
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_supplier_performance_export(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	dataset = _build_supplier_performance_dataset(_coerce_filters(filters))
	return {
		"title": dataset.get("title") or "",
		"columns": dataset.get("columns") or [],
		"rows": dataset.get("rows") or [],
		"summary": dataset.get("summary") or [],
		"company_currency": dataset.get("company_currency") or "",
		"scan": dataset.get("scan") or {},
		"metadata": dataset.get("metadata") or {},
	}


def _build_supplier_performance_dataset(filters: frappe._dict) -> dict[str, Any]:
	purchase_filters = frappe._dict(
		company=filters.get("company"),
		branch=filters.get("branch"),
		supplier=filters.get("supplier"),
		supplier_group=filters.get("supplier_group"),
		from_date=filters.get("from_date"),
		to_date=filters.get("to_date"),
		group_by="Supplier",
	)
	purchases = _build_purchase_analysis_dataset(purchase_filters)

	payables_filters = frappe._dict(
		company=filters.get("company"),
		branch=filters.get("branch"),
		supplier=filters.get("supplier"),
		supplier_group=filters.get("supplier_group"),
		as_of_date=nowdate(),
		ageing_bucket="All",
	)
	payables = get_supplier_payables_export(payables_filters)

	suppliers: dict[str, dict[str, Any]] = {}
	for row in purchases.get("rows") or []:
		supplier = str(row.get("group_key") or "").strip()
		if not supplier:
			continue
		bucket = suppliers.setdefault(supplier, _new_supplier_bucket(supplier, row.get("group_label")))
		_add_purchase_metrics(bucket, row)

	for row in payables.get("rows") or []:
		supplier = str(row.get("supplier") or "").strip()
		if not supplier:
			continue
		bucket = suppliers.setdefault(
			supplier,
			_new_supplier_bucket(supplier, row.get("supplier_name") or supplier),
		)
		if not bucket.get("supplier_name") or bucket.get("supplier_name") == supplier:
			bucket["supplier_name"] = str(row.get("supplier_name") or supplier)
		_add_payable_metrics(bucket, row)

	rows = [_finalise_supplier_bucket(bucket) for bucket in suppliers.values()]
	rows.sort(
		key=lambda row: (
			-flt(row.get("net_purchased")),
			-flt(row.get("current_outstanding")),
			str(row.get("supplier_name") or row.get("supplier") or ""),
		)
	)

	currency = str(purchases.get("company_currency") or payables.get("company_currency") or "")
	return {
		"title": _("Supplier Performance"),
		"columns": _columns(currency),
		"rows": rows,
		"summary": _summary(rows),
		"company_currency": currency,
		"scan": {
			"purchase_invoices": (purchases.get("scan") or {}).get("invoices", 0),
			"purchase_item_rows": (purchases.get("scan") or {}).get("item_rows", 0),
			"payable_invoices": (payables.get("scan") or {}).get("invoices", 0),
		},
		"metadata": {
			"purchase_basis": "Selected-period submitted Purchase Invoice item net amounts with returns reversed",
			"payables_basis": "Current ERPNext Supplier Payables outstanding balances aged at today",
			"payables_ageing_date": payables.get("ageing_date") or nowdate(),
			"historical_payables_supported": bool(payables.get("historical_balance_supported")),
			"branch_truth": "RetailEdge authoritative Purchase Invoice branch attribution",
			"supplier_score": "No composite supplier score is calculated or displayed.",
			"delivery_kpi": (
				"No on-time delivery rate is shown because this MVP view does not infer delivery performance "
				"from incomplete or truncated purchase-order evidence."
			),
			"control_owner": "Professional Purchasing remains the operational owner of PO receipt/billing attention states.",
		},
	}


def _new_supplier_bucket(supplier: str, supplier_name: Any = None) -> dict[str, Any]:
	return {
		"supplier": supplier,
		"supplier_name": str(supplier_name or supplier),
		"purchase_value": 0.0,
		"returns_value": 0.0,
		"net_purchased": 0.0,
		"invoice_count": 0,
		"current_outstanding": 0.0,
		"overdue_outstanding": 0.0,
		"open_bill_count": 0,
		"overdue_bill_count": 0,
		"oldest_overdue_days": 0,
	}


def _add_purchase_metrics(bucket: dict[str, Any], row: dict[str, Any]) -> None:
	bucket["purchase_value"] += flt(row.get("purchase_value"))
	bucket["returns_value"] += flt(row.get("returns_value"))
	bucket["net_purchased"] += flt(row.get("net_purchased"))
	bucket["invoice_count"] += cint(row.get("invoice_count"))


def _add_payable_metrics(bucket: dict[str, Any], row: dict[str, Any]) -> None:
	outstanding = flt(row.get("outstanding"))
	overdue_days = max(cint(row.get("overdue_days")), 0)
	bucket["current_outstanding"] += outstanding
	bucket["open_bill_count"] += 1
	if overdue_days > 0:
		bucket["overdue_outstanding"] += outstanding
		bucket["overdue_bill_count"] += 1
		bucket["oldest_overdue_days"] = max(cint(bucket.get("oldest_overdue_days")), overdue_days)


def _finalise_supplier_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
	row = dict(bucket)
	purchase_value = flt(row.get("purchase_value"))
	invoice_count = cint(row.get("invoice_count"))
	row["return_rate_percent"] = (
		flt(row.get("returns_value")) / purchase_value * 100.0 if purchase_value > 0 else None
	)
	row["average_invoice_value"] = (
		flt(row.get("net_purchased")) / invoice_count if invoice_count else 0.0
	)
	return row


def _summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	total_invoices = sum(cint(row.get("invoice_count")) for row in rows)
	net_purchased = sum(flt(row.get("net_purchased")) for row in rows)
	return [
		{"label": _("Net Purchased"), "value": net_purchased, "datatype": "Currency"},
		{
			"label": _("Returns"),
			"value": sum(flt(row.get("returns_value")) for row in rows),
			"datatype": "Currency",
		},
		{"label": _("Purchase Invoices"), "value": total_invoices, "datatype": "Int"},
		{"label": _("Suppliers"), "value": len(rows), "datatype": "Int"},
		{
			"label": _("Current Outstanding"),
			"value": sum(flt(row.get("current_outstanding")) for row in rows),
			"datatype": "Currency",
		},
		{
			"label": _("Overdue Outstanding"),
			"value": sum(flt(row.get("overdue_outstanding")) for row in rows),
			"datatype": "Currency",
		},
	]


def _columns(currency: str) -> list[dict[str, Any]]:
	return [
		{"fieldname": "supplier", "label": _("Supplier"), "fieldtype": "Link", "options": "Supplier"},
		{"fieldname": "supplier_name", "label": _("Supplier Name"), "fieldtype": "Data"},
		{"fieldname": "purchase_value", "label": _("Purchase Value"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "returns_value", "label": _("Returns"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "net_purchased", "label": _("Net Purchased"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "invoice_count", "label": _("Invoices"), "fieldtype": "Int"},
		{"fieldname": "average_invoice_value", "label": _("Avg Invoice Value"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "return_rate_percent", "label": _("Return Rate"), "fieldtype": "Percent"},
		{"fieldname": "current_outstanding", "label": _("Current Outstanding"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "overdue_outstanding", "label": _("Overdue Outstanding"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "open_bill_count", "label": _("Open Bills"), "fieldtype": "Int"},
		{"fieldname": "overdue_bill_count", "label": _("Overdue Bills"), "fieldtype": "Int"},
		{"fieldname": "oldest_overdue_days", "label": _("Oldest Overdue"), "fieldtype": "Int"},
	]
