from __future__ import annotations

from typing import Any

import frappe

from retailedge.expense_budget import build_expense_budget_insight
from retailedge.expense_register import get_expense_register_export


@frappe.whitelist()
def get_expense_budget_insight(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	resolved = frappe._dict(filters or {})
	company = str(resolved.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(resolved.get("branch") or "").strip()
	period_filters = {
		"company": company,
		"branch": branch,
		"from_date": resolved.get("from_date"),
		"to_date": resolved.get("to_date"),
		"expense_category": resolved.get("expense_category") or "",
		"expense_status": resolved.get("expense_status") or "",
	}
	actual = get_expense_register_export(period_filters)
	return build_expense_budget_insight(
		company=company,
		branch=branch,
		from_date=period_filters.get("from_date"),
		to_date=period_filters.get("to_date"),
		expense_rows=list(actual.get("rows") or []),
	)
