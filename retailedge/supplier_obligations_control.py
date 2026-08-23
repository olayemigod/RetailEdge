from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.supplier_payables import get_supplier_payables_export

DASHBOARD_KEY = "owner-dashboard"
MAX_PRIORITY_ROWS = 20
MAX_SUPPLIER_EXPOSURES = 10


@frappe.whitelist()
def get_supplier_obligations_control(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	resolved = _coerce_filters(filters)
	company = str(resolved.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	branch = str(resolved.get("branch") or "").strip()
	require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)
	resolved.company = company
	resolved.as_of_date = nowdate()

	payables = get_supplier_payables_export(resolved)
	rows = list(payables.get("rows") or [])
	return _build_supplier_control(payables, rows)


def _build_supplier_control(payables: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
	total = sum(flt(row.get("outstanding")) for row in rows)
	overdue = sum(flt(row.get("outstanding")) for row in rows if int(row.get("overdue_days") or 0) > 0)
	over_90 = sum(flt(row.get("outstanding")) for row in rows if int(row.get("overdue_days") or 0) > 90)
	by_supplier: dict[str, dict[str, Any]] = defaultdict(lambda: {"outstanding": 0.0, "overdue": 0.0, "open_bills": 0})
	for row in rows:
		key = str(row.get("supplier") or row.get("supplier_name") or "").strip()
		entry = by_supplier[key]
		entry["supplier"] = key
		entry["supplier_name"] = row.get("supplier_name") or key
		entry["outstanding"] += flt(row.get("outstanding"))
		entry["open_bills"] += 1
		if int(row.get("overdue_days") or 0) > 0:
			entry["overdue"] += flt(row.get("outstanding"))

	exposures = sorted(by_supplier.values(), key=lambda item: (-flt(item["outstanding"]), str(item["supplier"])))
	for entry in exposures:
		entry["share_percent"] = _percent(flt(entry["outstanding"]), total)
	top_supplier_share = exposures[0]["share_percent"] if exposures else None
	top_five_share = _percent(sum(flt(item["outstanding"]) for item in exposures[:5]), total)

	priority = [_priority_row(row) for row in rows if int(row.get("overdue_days") or 0) > 0]
	priority.sort(key=lambda item: (item["priority_rank"], -item["overdue_days"], -flt(item["outstanding"]), item["invoice"]))
	oldest = sorted(
		(row for row in rows if int(row.get("overdue_days") or 0) > 0),
		key=lambda row: (-int(row.get("overdue_days") or 0), str(row.get("due_date") or ""), str(row.get("invoice") or "")),
	)[:MAX_PRIORITY_ROWS]

	return {
		"title": _("Supplier Obligations Control"),
		"balance_basis": payables.get("balance_basis") or "current_outstanding",
		"ageing_date": payables.get("ageing_date") or nowdate(),
		"historical_balance_supported": False,
		"summary": [
			_card("Total Payables", total, "Currency"),
			_card("Overdue", overdue, "Currency"),
			_card("Over 90 Days", over_90, "Currency"),
			_card("Overdue Pressure", _percent(overdue, total), "Percent"),
			_card("Top Supplier Concentration", top_supplier_share, "Percent"),
		],
		"concentration": {
			"top_supplier_percent": top_supplier_share,
			"top_five_suppliers_percent": top_five_share,
			"supplier_count": len(exposures),
		},
		"supplier_exposure": exposures[:MAX_SUPPLIER_EXPOSURES],
		"payment_priorities": priority[:MAX_PRIORITY_ROWS],
		"oldest_overdue": [_invoice_row(row) for row in oldest],
		"scan": payables.get("scan") or {},
		"metadata": {
			"accounting_truth": "Current submitted ERPNext Purchase Invoice outstanding balances remain authoritative.",
			"priority_definition": "Ageing-based payment attention only; it does not override contractual terms, disputes, cash planning or management approval.",
			"native_drill_through": "Purchase Invoice routes must open in a new tab from EdgeSuite pages.",
			"authorization": "Owner Dashboard view capability plus underlying Purchase Invoice, Company and Branch permissions.",
		},
	}


def _priority_row(row: dict[str, Any]) -> dict[str, Any]:
	days = int(row.get("overdue_days") or 0)
	if days > 90:
		priority, rank = "Critical", 0
	elif days > 60:
		priority, rank = "High", 1
	elif days > 30:
		priority, rank = "Medium", 2
	else:
		priority, rank = "Watch", 3
	return {**_invoice_row(row), "priority": _(priority), "priority_rank": rank}


def _invoice_row(row: dict[str, Any]) -> dict[str, Any]:
	invoice = str(row.get("invoice") or "")
	return {
		"invoice": invoice,
		"supplier": row.get("supplier") or "",
		"supplier_name": row.get("supplier_name") or row.get("supplier") or "",
		"branch": row.get("branch") or "",
		"posting_date": row.get("posting_date"),
		"due_date": row.get("due_date"),
		"outstanding": flt(row.get("outstanding")),
		"overdue_days": int(row.get("overdue_days") or 0),
		"ageing_bucket": row.get("ageing_bucket") or "",
		"route": f"/app/purchase-invoice/{invoice}" if invoice else "",
		"open_in_new_tab": True,
	}


def _percent(numerator: float, denominator: float) -> float | None:
	return numerator / denominator * 100.0 if denominator else None


def _card(label: str, value: float | None, datatype: str) -> dict[str, Any]:
	return {"label": _(label), "value": value, "datatype": datatype, "time_basis": "current"}


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
