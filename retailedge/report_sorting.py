from __future__ import annotations

import json
from datetime import date, datetime
from functools import cmp_to_key
from numbers import Number
from typing import Any, Iterable, Mapping

REPORT_SORT_DIRECTIONS = frozenset({"asc", "desc"})

REPORT_SORT_FIELDS: dict[str, frozenset[str]] = {
	"cash-flow-outlook": frozenset({"period_label", "period_start", "period_end", "receivables_due", "payables_due", "net_scheduled", "cumulative_scheduled_net", "receivable_rows", "payable_rows"}),
	"cash-movement": frozenset({"posting_date", "account", "branch", "movement_type", "payment_method", "money_in", "money_out", "net_change", "voucher_type", "voucher_no"}),
	"cash-shift-verification": frozenset({"company", "branch", "pos_profile", "cashier", "opening_shift", "closing_shift", "shift_date", "opening_cash", "cash_sales", "included_cashier_expenses", "cash_deposits", "expected_cash", "actual_closing_cash", "cash_variance", "cash_status", "eligible_cash_invoices", "synced_cash_invoices", "daily_sales_audit", "review_status"}),
	"customer-receivables": frozenset({"customer", "customer_name", "invoice", "branch", "posting_date", "due_date", "outstanding", "overdue_days", "ageing_bucket", "status", "payment_request", "payment_request_status", "dunning", "collection_status"}),
	"daily-sales-audit": frozenset({"name", "audit_date", "company", "branch", "pos_profile", "cashier", "pos_opening_shift", "pos_closing_shift", "opening_cash_amount", "cash_sales_amount", "cashier_expense_amount", "cash_deposit_amount", "expected_cash_amount", "actual_closing_cash_amount", "cash_variance_amount", "net_variance_amount", "audit_status", "audit_result", "clarification_required", "submitted_for_review_by", "submitted_for_review_on", "approved_by", "approved_on", "rejected_by", "rejected_on", "review_required"}),
	"expense-register": frozenset({"name", "expense_date", "branch", "cashier", "expense_category", "amount", "expense_status", "ledger_status", "posting_ready", "description", "source_type", "source_reference", "expense_account", "cost_center", "payment_account"}),
	"expense-review": frozenset({"name", "expense_date", "branch", "cashier", "expense_category", "amount", "expense_status", "daily_audit_inclusion_status", "daily_audit_classification", "posting_ready", "posting_block_reason", "ledger_status"}),
	"purchase-register": frozenset({"invoice", "posting_date", "due_date", "supplier", "supplier_name", "branch", "invoice_type", "transaction_currency", "net_amount", "tax_amount", "grand_total", "outstanding", "status", "return_against"}),
	"supplier-payables": frozenset({"supplier", "supplier_name", "invoice", "branch", "posting_date", "due_date", "outstanding", "overdue_days", "ageing_bucket", "status"}),
	"sales-by-item": frozenset({"item_code", "item_name", "item_group", "stock_uom", "sold_qty", "returned_qty", "net_qty", "sales_value", "returns_value", "net_sales", "invoice_count", "average_selling_price"}),
	"sales-invoice-register": frozenset({"invoice", "posting_date", "customer", "customer_name", "branch", "salespeople", "invoice_type", "transaction_currency", "net_amount", "tax_amount", "grand_total", "outstanding", "status", "return_against"}),
	"stock-accounting-integrity": frozenset({"name", "ledger_type", "posting_date", "posting_time", "voucher_type", "voucher_no", "stock_value", "account_value", "difference_value"}),
	"stock-position": frozenset({"item_code", "item_name", "item_group", "stock_uom", "actual_qty", "reserved_qty", "available_qty", "ordered_qty", "projected_qty", "stock_status", "replenishment_status", "reorder_due_location_count", "suggested_reorder_qty", "reorder_due_warehouses", "valuation_rate", "stock_value"}),
}


def report_sort_fields(report_key: str) -> frozenset[str]:
	return REPORT_SORT_FIELDS.get(str(report_key or "").strip(), frozenset())


def normalise_report_sort(sort: Mapping[str, Any] | str | None, report_key: str) -> dict[str, str] | None:
	if isinstance(sort, str):
		try:
			sort = json.loads(sort)
		except (TypeError, ValueError, json.JSONDecodeError):
			return None
	if not isinstance(sort, Mapping):
		return None
	field = str(sort.get("field") or sort.get("fieldname") or sort.get("key") or "").strip()
	direction = str(sort.get("direction") or sort.get("order") or "").strip().lower()
	if field not in report_sort_fields(report_key) or direction not in REPORT_SORT_DIRECTIONS:
		return None
	return {"field": field, "direction": direction}


def _comparable(value: Any) -> tuple[bool, int, Any]:
	if value is None or value == "":
		return True, 99, None
	if isinstance(value, bool):
		return False, 0, int(value)
	if isinstance(value, Number):
		return False, 0, value
	if isinstance(value, datetime):
		return False, 1, value.timestamp()
	if isinstance(value, date):
		return False, 1, value.toordinal()
	text = str(value).strip()
	try:
		if len(text) >= 10 and text[4] == "-" and text[7] == "-":
			return False, 1, datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
	except (TypeError, ValueError, OverflowError):
		pass
	return False, 2, text.casefold()


def sort_materialized_rows(
	rows: Iterable[Mapping[str, Any]],
	sort: Mapping[str, Any] | str | None,
	report_key: str,
) -> tuple[list[Mapping[str, Any]], dict[str, str] | None]:
	resolved = list(rows or [])
	normalized = normalise_report_sort(sort, report_key)
	if not normalized:
		return resolved, None
	field = normalized["field"]
	factor = -1 if normalized["direction"] == "desc" else 1

	def compare(left: tuple[int, Mapping[str, Any]], right: tuple[int, Mapping[str, Any]]) -> int:
		left_index, left_row = left
		right_index, right_row = right
		left_empty, left_kind, left_value = _comparable(left_row.get(field))
		right_empty, right_kind, right_value = _comparable(right_row.get(field))
		if left_empty and right_empty:
			return left_index - right_index
		if left_empty:
			return 1
		if right_empty:
			return -1
		if left_kind != right_kind:
			comparison = -1 if left_kind < right_kind else 1
		elif left_value < right_value:
			comparison = -1
		elif left_value > right_value:
			comparison = 1
		else:
			comparison = 0
		return comparison * factor if comparison else left_index - right_index

	indexed = list(enumerate(resolved))
	indexed.sort(key=cmp_to_key(compare))
	return [row for _, row in indexed], normalized


def mark_report_columns(columns: Iterable[Mapping[str, Any]], report_key: str) -> list[dict[str, Any]]:
	allowed = report_sort_fields(report_key)
	result: list[dict[str, Any]] = []
	for raw in columns or []:
		column = dict(raw or {})
		field = str(column.get("fieldname") or column.get("key") or "").strip()
		column["sortable"] = bool(field and field in allowed and column.get("sortable") is not False)
		result.append(column)
	return result


def apply_materialized_report_sort(
	dataset: dict[str, Any],
	sort: Mapping[str, Any] | str | None,
	report_key: str,
) -> dict[str, str] | None:
	rows, normalized = sort_materialized_rows(dataset.get("rows") or [], sort, report_key)
	dataset["rows"] = rows
	dataset["columns"] = mark_report_columns(dataset.get("columns") or [], report_key)
	dataset["sort"] = normalized
	return normalized


def build_report_order_by(
	sort: Mapping[str, Any] | str | None,
	report_key: str,
	order_fields: Mapping[str, str],
	*,
	default_order: str,
	tie_breakers: Iterable[str] = (),
) -> tuple[dict[str, str] | None, str]:
	normalized = normalise_report_sort(sort, report_key)
	if not normalized:
		return None, default_order
	expression = order_fields.get(normalized["field"])
	if not expression:
		return None, default_order
	parts = [f"{expression} {normalized['direction'].upper()}"]
	parts.extend(str(value).strip() for value in tie_breakers if str(value).strip())
	return normalized, ", ".join(parts)
