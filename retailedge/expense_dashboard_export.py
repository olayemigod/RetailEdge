from __future__ import annotations

from typing import Any

from frappe import _

from retailedge.expense_budget_api import get_expense_budget_insight
from retailedge.expense_dashboard import build_expense_dashboard_export_dataset


def build_expense_dashboard_export_with_budget(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	dataset = build_expense_dashboard_export_dataset(filters)
	rows = list(dataset.get("rows") or [])
	budget = get_expense_budget_insight(filters)
	if budget.get("available"):
		for label, fieldname in (
			("Budget for Period", "target_amount"),
			("Actual Spend", "actual_amount"),
			("Budget Remaining", "remaining_amount"),
			("Projected Period Spend", "projected_period_spend"),
			("Projected Variance", "projected_variance"),
		):
			rows.append(
				{
					"section": _("Budget & Burn Rate"),
					"dimension": _("ERPNext Budget"),
					"metric": _(label),
					"value": budget.get(fieldname),
				}
			)
		for row in budget.get("category_targets") or []:
			if row.get("target") is None:
				continue
			rows.append(
				{
					"section": _("Category Budget"),
					"dimension": row.get("category") or "",
					"metric": _("Budget Target"),
					"value": row.get("target"),
				}
			)
	return {**dataset, "rows": rows}
