from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate

EXPENSE_CATEGORY_DOCTYPE = "RetailEdge Expense Category"
BRANCH_PROFILE_DOCTYPE = "RetailEdge Branch Profile"
BUDGET_DOCTYPE = "Budget"
MAX_BUDGET_ROWS = 500
MAX_CATEGORY_ROWS = 500


def build_expense_budget_insight(
	*,
	company: str,
	branch: str,
	from_date,
	to_date,
	expense_rows: list[dict[str, Any]],
) -> dict[str, Any]:
	"""Return planning insight from submitted native ERPNext Budgets.

	This is read-only planning metadata. It never creates, mutates, submits, or enforces a Budget.
	Actual expense truth continues to come from RetailEdge Expense Register.
	"""
	if not company or not from_date or not to_date:
		return _unavailable("A Company and date range are required for budget comparison.")
	if not frappe.db.exists("DocType", BUDGET_DOCTYPE):
		return _unavailable("ERPNext Budget is unavailable on this site.")
	if not frappe.has_permission(BUDGET_DOCTYPE, "read"):
		return _unavailable("Your current permissions do not allow ERPNext Budget insight.")

	start = getdate(from_date)
	end = getdate(to_date)
	if start > end:
		return _unavailable("From Date cannot be after To Date.")

	categories = _category_mappings(company=company, branch=branch)
	if not categories:
		return _unavailable("No RetailEdge Expense Categories have a usable Expense Account and Cost Center mapping.")

	pairs = sorted({(row["expense_account"], row["cost_center"]) for row in categories})
	budgets = _matching_budgets(company=company, pairs=pairs, start=start, end=end)
	pair_targets: dict[tuple[str, str], float] = defaultdict(float)
	budget_names: set[str] = set()
	for budget in budgets:
		pair = (str(budget.get("account") or ""), str(budget.get("cost_center") or ""))
		if pair not in pairs:
			continue
		pair_targets[pair] += _allocated_budget_amount(budget, start=start, end=end)
		if budget.get("name"):
			budget_names.add(str(budget["name"]))

	actual_by_category: dict[str, float] = defaultdict(float)
	for row in expense_rows:
		category = str(row.get("expense_category") or "").strip()
		if category:
			actual_by_category[category] += flt(row.get("amount"))

	pair_categories: dict[tuple[str, str], list[str]] = defaultdict(list)
	for row in categories:
		pair_categories[(row["expense_account"], row["cost_center"])].append(row["category"])

	category_targets: list[dict[str, Any]] = []
	for row in categories:
		pair = (row["expense_account"], row["cost_center"])
		mapped_categories = sorted(set(pair_categories[pair]))
		ambiguous = len(mapped_categories) > 1
		target = None if ambiguous else flt(pair_targets.get(pair))
		actual = flt(actual_by_category.get(row["category"]))
		category_targets.append(
			{
				"category": row["category"],
				"expense_account": row["expense_account"],
				"cost_center": row["cost_center"],
				"actual": actual,
				"target": target,
				"variance": (target - actual) if target is not None else None,
				"used_pct": (actual / target * 100) if target and target > 0 else None,
				"ambiguous": ambiguous,
				"shared_with": [name for name in mapped_categories if name != row["category"]],
			}
		)

	total_target = sum(flt(amount) for amount in pair_targets.values())
	total_actual = sum(flt(row.get("amount")) for row in expense_rows)
	period_days = max(1, date_diff(end, start) + 1)
	elapsed_days = _elapsed_days(start=start, end=end)
	projected = (total_actual / elapsed_days * period_days) if elapsed_days else total_actual
	remaining = total_target - total_actual
	used_pct = (total_actual / total_target * 100) if total_target > 0 else None
	projected_variance = total_target - projected if total_target > 0 else None

	return {
		"available": bool(total_target > 0),
		"reason": "" if total_target > 0 else _("No submitted ERPNext Budget matched the mapped expense accounts/cost centres for this period."),
		"source": "ERPNext Budget",
		"target_amount": total_target,
		"actual_amount": total_actual,
		"remaining_amount": remaining if total_target > 0 else None,
		"used_pct": used_pct,
		"elapsed_days": elapsed_days,
		"period_days": period_days,
		"projected_period_spend": projected,
		"projected_variance": projected_variance,
		"projected_over_budget": bool(total_target > 0 and projected > total_target),
		"over_budget": bool(total_target > 0 and total_actual > total_target),
		"budget_count": len(budget_names),
		"mapped_pair_count": len(pairs),
		"category_targets": sorted(category_targets, key=lambda row: (-flt(row["actual"]), row["category"])),
		"ambiguous_category_count": sum(1 for row in category_targets if row["ambiguous"]),
		"branch_cost_center": _branch_expense_cost_center(company=company, branch=branch) if branch else "",
		"enforcement_note": _("RetailEdge displays native ERPNext Budget insight here but does not change ERPNext Budget enforcement or workflow settings."),
	}


def _category_mappings(*, company: str, branch: str) -> list[dict[str, str]]:
	branch_cost_center = _branch_expense_cost_center(company=company, branch=branch) if branch else ""
	filters: dict[str, Any] = {"is_active": 1}
	rows = frappe.get_list(
		EXPENSE_CATEGORY_DOCTYPE,
		filters=filters,
		fields=["name", "company", "expense_account", "default_cost_center"],
		order_by="name asc",
		limit_page_length=MAX_CATEGORY_ROWS,
	)
	result: list[dict[str, str]] = []
	for row in rows:
		row_company = str(row.get("company") or "").strip()
		if row_company and row_company != company:
			continue
		account = str(row.get("expense_account") or "").strip()
		cost_center = branch_cost_center or str(row.get("default_cost_center") or "").strip()
		if not account or not cost_center:
			continue
		account_company = frappe.db.get_value("Account", account, "company")
		cost_center_company = frappe.db.get_value("Cost Center", cost_center, "company")
		if account_company != company or cost_center_company != company:
			continue
		result.append(
			{
				"category": str(row.get("name") or ""),
				"expense_account": account,
				"cost_center": cost_center,
			}
		)
	return result


def _branch_expense_cost_center(*, company: str, branch: str) -> str:
	if not branch or not frappe.db.exists("DocType", BRANCH_PROFILE_DOCTYPE):
		return ""
	row = frappe.get_list(
		BRANCH_PROFILE_DOCTYPE,
		filters={"company": company, "branch": branch, "enabled": 1},
		fields=["default_expense_cost_center", "default_cost_center"],
		order_by="is_default_for_company desc, modified desc",
		limit_page_length=1,
	)
	if not row:
		return ""
	return str(row[0].get("default_expense_cost_center") or row[0].get("default_cost_center") or "").strip()


def _matching_budgets(
	*,
	company: str,
	pairs: list[tuple[str, str]],
	start: date,
	end: date,
) -> list[dict[str, Any]]:
	if not pairs:
		return []
	accounts = sorted({pair[0] for pair in pairs})
	cost_centers = sorted({pair[1] for pair in pairs})
	rows = frappe.get_list(
		BUDGET_DOCTYPE,
		filters={
			"docstatus": 1,
			"company": company,
			"budget_against": "Cost Center",
			"account": ["in", accounts],
			"cost_center": ["in", cost_centers],
			"budget_start_date": ["<=", end],
			"budget_end_date": [">=", start],
		},
		fields=[
			"name",
			"account",
			"cost_center",
			"budget_amount",
			"budget_start_date",
			"budget_end_date",
		],
		order_by="budget_start_date asc, name asc",
		limit_page_length=MAX_BUDGET_ROWS + 1,
	)
	if len(rows) > MAX_BUDGET_ROWS:
		frappe.throw(_("More than {0} ERPNext Budgets match this expense scope. Narrow the business scope before loading budget insight.").format(MAX_BUDGET_ROWS))
	result: list[dict[str, Any]] = []
	for row in rows:
		budget = dict(row)
		budget["distribution"] = frappe.get_all(
			"Budget Distribution",
			filters={"parent": row.name, "parenttype": BUDGET_DOCTYPE},
			fields=["start_date", "end_date", "amount"],
			order_by="start_date asc, idx asc",
			limit_page_length=100,
		)
		result.append(budget)
	return result


def _allocated_budget_amount(budget: dict[str, Any], *, start: date, end: date) -> float:
	distribution = list(budget.get("distribution") or [])
	if distribution:
		return sum(_overlap_allocated_amount(row, start=start, end=end) for row in distribution)
	budget_start = getdate(budget.get("budget_start_date"))
	budget_end = getdate(budget.get("budget_end_date"))
	return _prorated_amount(
		flt(budget.get("budget_amount")),
		period_start=budget_start,
		period_end=budget_end,
		start=start,
		end=end,
	)


def _overlap_allocated_amount(row: dict[str, Any], *, start: date, end: date) -> float:
	return _prorated_amount(
		flt(row.get("amount")),
		period_start=getdate(row.get("start_date")),
		period_end=getdate(row.get("end_date")),
		start=start,
		end=end,
	)


def _prorated_amount(
	amount: float,
	*,
	period_start: date,
	period_end: date,
	start: date,
	end: date,
) -> float:
	overlap_start = max(period_start, start)
	overlap_end = min(period_end, end)
	if overlap_start > overlap_end:
		return 0.0
	period_days = max(1, date_diff(period_end, period_start) + 1)
	overlap_days = date_diff(overlap_end, overlap_start) + 1
	return flt(amount) * overlap_days / period_days


def _elapsed_days(*, start: date, end: date) -> int:
	today = getdate()
	if today < start:
		return 0
	return max(1, date_diff(min(today, end), start) + 1)


def _unavailable(reason: str) -> dict[str, Any]:
	return {
		"available": False,
		"reason": _(reason),
		"source": "ERPNext Budget",
		"target_amount": None,
		"actual_amount": None,
		"remaining_amount": None,
		"used_pct": None,
		"projected_period_spend": None,
		"projected_variance": None,
		"projected_over_budget": False,
		"over_budget": False,
		"budget_count": 0,
		"category_targets": [],
		"ambiguous_category_count": 0,
	}
