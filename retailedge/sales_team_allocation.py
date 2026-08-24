from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.sales_reporting import MAX_SALES_TEAM_ROWS

UNALLOCATED_SALESPERSON = "Unallocated Sales Team"
UNASSIGNED_SALESPERSON = "Unassigned Salesperson"
ALLOCATION_TOLERANCE = 0.000001


def resolve_sales_team_allocations(
	team_rows: list[frappe._dict] | list[dict[str, Any]],
	*,
	invoice: str = "",
) -> list[tuple[str, float]]:
	"""Resolve one invoice's Sales Team into weights that never exceed 100%.

	Contract shared by profitability and salesperson intelligence:
	- positive allocated percentages are respected;
	- positive allocations above 100% are rejected;
	- a positive allocation total below 100% leaves an explicit unallocated residual;
	- when every allocation is zero/missing, the invoice is split evenly across named team members;
	- no named Sales Team rows produces an explicit unassigned salesperson bucket.
	"""
	team = [row for row in team_rows if str(row.get("sales_person") or "").strip()]
	if not team:
		return [(_(UNASSIGNED_SALESPERSON), 1.0)]

	positive = [
		(str(row.get("sales_person")), max(flt(row.get("allocated_percentage")), 0.0) / 100.0)
		for row in team
		if flt(row.get("allocated_percentage")) > 0
	]
	total_weight = sum(weight for _salesperson, weight in positive)
	if positive:
		if total_weight > 1.0 + ALLOCATION_TOLERANCE:
			label = invoice or _("the selected Sales Invoice")
			frappe.throw(
				_("Sales Team allocation on Sales Invoice {0} exceeds 100%. Correct the invoice allocation before using salesperson intelligence.").format(label)
			)
		allocations = list(positive)
		if total_weight < 1.0 - ALLOCATION_TOLERANCE:
			allocations.append((_(UNALLOCATED_SALESPERSON), 1.0 - total_weight))
		return allocations

	weight = 1.0 / len(team)
	return [(str(row.get("sales_person")), weight) for row in team]


def get_sales_team_allocations(invoice_names: list[str]) -> dict[str, list[tuple[str, float]]]:
	"""Load bounded Sales Team rows and resolve each invoice with the shared contract."""
	if not invoice_names:
		return {}
	rows = frappe.get_all(
		"Sales Team",
		filters={"parent": ["in", invoice_names], "parenttype": "Sales Invoice"},
		fields=["parent", "sales_person", "allocated_percentage"],
		order_by="parent asc, idx asc",
		limit=MAX_SALES_TEAM_ROWS + 1,
	)
	if len(rows) > MAX_SALES_TEAM_ROWS:
		frappe.throw(
			_("More than {0} Sales Team rows match this scope. Narrow the date range or Branch.").format(
				MAX_SALES_TEAM_ROWS
			)
		)
	by_invoice: dict[str, list[frappe._dict]] = defaultdict(list)
	for row in rows:
		by_invoice[str(row.parent)].append(row)

	return {
		invoice: resolve_sales_team_allocations(team, invoice=invoice)
		for invoice, team in by_invoice.items()
	}
