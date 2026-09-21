from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import flt, getdate

from retailedge.branch_context import user_has_global_branch_access
from retailedge.cash_movement import get_cash_movement_export
from retailedge.customer_receivables import get_customer_receivables_export
from retailedge.expense_register import get_expense_register_export
from retailedge.operating_context import get_operational_branch_scope, validate_operating_branch
from retailedge.sales_reporting import get_sales_by_item_export, get_sales_invoice_register_export
from retailedge.stock_position import get_stock_position
from retailedge.supplier_payables import get_supplier_payables_export


MAX_VISUAL_PERIOD_DAYS = 366
TOP_MIX_ROWS = 6
AGE_BUCKETS = ("Current", "1-30 Days", "31-60 Days", "61-90 Days", "91+ Days")


@frappe.whitelist()
def get_business_hub_visuals(
    company: str = "",
    branch: str = "",
    from_date: str = "",
    to_date: str = "",
) -> dict[str, Any]:
    """Return compact, permission-aware visual datasets for the Business Hub."""
    company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
    branch = str(branch or "").strip()
    if not company:
        frappe.throw(_("Company is required."))

    branch, scope_error = _resolve_scope(company=company, branch=branch)
    start, end = _validated_period(from_date=from_date, to_date=to_date)
    currency = str(frappe.get_cached_value("Company", company, "default_currency") or "")

    if scope_error:
        return {
            "company": company,
            "branch": "",
            "currency": currency,
            "from_date": str(start),
            "to_date": str(end),
            "granularity": _granularity(start, end),
            "visuals": _unavailable_visuals(scope_error),
        }

    period_filters = {
        "company": company,
        "branch": branch,
        "from_date": str(start),
        "to_date": str(end),
    }
    current_filters = {"company": company, "branch": branch}

    visuals = [
        _safe_visual(
            key="sales_trend",
            title=_("Sales Trend"),
            route="/app/sales-invoice-register",
            time_basis="period",
            loader=lambda: _sales_trend(period_filters, start=start, end=end, currency=currency),
        ),
        _safe_visual(
            key="sales_mix",
            title=_("Sales Mix"),
            route="/app/sales-by-item" if branch else "/app/branch-performance-dashboard",
            time_basis="period",
            loader=lambda: _sales_mix(period_filters, branch=branch, currency=currency),
        ),
        _safe_visual(
            key="cash_flow",
            title=_("Cash In vs Cash Out"),
            route="/app/cash-movement",
            time_basis="period",
            loader=lambda: _cash_visual(period_filters, start=start, end=end, currency=currency),
        ),
        _safe_visual(
            key="expense_mix",
            title=_("Expense Mix"),
            route="/app/expense-register",
            time_basis="period",
            loader=lambda: _expense_visual(period_filters, currency=currency),
        ),
        _safe_visual(
            key="exposure",
            title=_("Receivables vs Payables"),
            route="/app/customer-receivables",
            time_basis="current",
            loader=lambda: _exposure_visual(current_filters, currency=currency),
        ),
        _safe_visual(
            key="stock_health",
            title=_("Stock Health"),
            route="/app/stock-position",
            time_basis="current",
            loader=lambda: _stock_health(current_filters),
        ),
    ]
    return {
        "company": company,
        "branch": branch,
        "currency": currency,
        "from_date": str(start),
        "to_date": str(end),
        "granularity": _granularity(start, end),
        "visuals": visuals,
        "metadata": {
            "composition": "existing_retailedge_reporting_authorities",
            "sales_truth": "submitted_sales_invoice",
            "cash_truth": "posted_cash_and_bank_gl_entries",
            "expense_truth": "consolidated_posted_expense_reporting",
            "receivable_payable_truth": "current_erpnext_outstanding",
            "stock_truth": "current_bin_and_item_reorder_state",
        },
    }


def _resolve_scope(*, company: str, branch: str) -> tuple[str, str]:
    user = frappe.session.user
    scope = get_operational_branch_scope(company, user=user)
    allowed = [
        str(value or "").strip()
        for value in scope.get("allowed_branches") or []
        if str(value or "").strip()
    ]
    if branch:
        if scope.get("restricted") and branch not in allowed:
            frappe.throw(
                _("You do not have active RetailEdge Branch access to Branch {0}.").format(branch),
                frappe.PermissionError,
            )
        validate_operating_branch(company=company, branch=branch, user=user, throw=True)
        return branch, ""

    if scope.get("restricted"):
        if len(allowed) == 1:
            validate_operating_branch(company=company, branch=allowed[0], user=user, throw=True)
            return allowed[0], ""
        if not allowed:
            return "", _("Your RetailEdge Branch access is not active for this Company.")
        return "", _("Choose a Branch to load scoped business visuals.")

    if not (
        user_has_global_branch_access(user=user)
        or frappe.has_permission("Company", "read", doc=company)
    ):
        frappe.throw(_("You do not have permission to view this Company."), frappe.PermissionError)
    return "", ""


def _validated_period(*, from_date: str, to_date: str):
    if not from_date or not to_date:
        frappe.throw(_("From Date and To Date are required for Business Hub visuals."))
    start = getdate(from_date)
    end = getdate(to_date)
    if start > end:
        frappe.throw(_("From Date cannot be after To Date."))
    if (end - start).days + 1 > MAX_VISUAL_PERIOD_DAYS:
        frappe.throw(
            _("Business Hub visuals support up to {0} days per request.").format(
                MAX_VISUAL_PERIOD_DAYS
            )
        )
    return start, end


def _safe_visual(
    *,
    key: str,
    title: str,
    route: str,
    time_basis: str,
    loader: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    previous_messages = list(getattr(frappe.local, "message_log", []) or [])
    try:
        payload = loader() or {}
        return {
            "key": key,
            "title": title,
            "available": True,
            "route": route,
            "time_basis": time_basis,
            **payload,
        }
    except (frappe.PermissionError, frappe.ValidationError) as exc:
        return {
            "key": key,
            "title": title,
            "available": False,
            "route": route,
            "time_basis": time_basis,
            "reason": str(exc),
            "rows": [],
            "series": [],
        }
    finally:
        frappe.local.message_log = previous_messages


def _sales_trend(
    filters: dict[str, Any],
    *,
    start,
    end,
    currency: str,
) -> dict[str, Any]:
    dataset = get_sales_invoice_register_export(filters)
    granularity = _granularity(start, end)
    rows = _period_rows(start, end, granularity, ("net_sales", "transactions"))
    by_key = {row["key"]: row for row in rows}
    for source in dataset.get("rows") or []:
        key, _ = _bucket_for_date(source.get("posting_date"), granularity)
        if key not in by_key:
            continue
        by_key[key]["net_sales"] += flt(source.get("grand_total"))
        by_key[key]["transactions"] += 1
    return {
        "description": _("Net invoiced sales over the selected period."),
        "chart_type": "line",
        "currency": currency,
        "granularity": granularity,
        "series": [
            {"key": "net_sales", "label": _("Net Sales"), "datatype": "Currency"},
        ],
        "rows": rows,
        "route_filters": dict(filters),
    }


def _sales_mix(
    filters: dict[str, Any],
    *,
    branch: str,
    currency: str,
) -> dict[str, Any]:
    if branch:
        dataset = get_sales_by_item_export(filters)
        buckets: dict[str, float] = defaultdict(float)
        for row in dataset.get("rows") or []:
            label = str(row.get("item_group") or _("Unspecified")).strip() or _("Unspecified")
            buckets[label] += flt(row.get("net_sales"))
        title = _("Sales by Category")
        description = _("Top item groups contributing to net sales in this Branch.")
        route = "/app/sales-by-item"
    else:
        dataset = get_sales_invoice_register_export(filters)
        buckets = defaultdict(float)
        for row in dataset.get("rows") or []:
            label = str(row.get("branch") or _("Unattributed")).strip() or _("Unattributed")
            buckets[label] += flt(row.get("grand_total"))
        title = _("Sales by Branch")
        description = _("Top Branch contributions to company net invoiced sales.")
        route = "/app/branch-performance-dashboard"

    return {
        "title": title,
        "description": description,
        "chart_type": "bar",
        "currency": currency,
        "series": [{"key": "value", "label": _("Net Sales"), "datatype": "Currency"}],
        "rows": _top_mix_rows(buckets),
        "route": route,
        "route_filters": dict(filters),
    }


def _cash_visual(
    filters: dict[str, Any],
    *,
    start,
    end,
    currency: str,
) -> dict[str, Any]:
    dataset = get_cash_movement_export(filters)
    granularity = _granularity(start, end)
    rows = _period_rows(start, end, granularity, ("money_in", "money_out"))
    by_key = {row["key"]: row for row in rows}
    for source in dataset.get("rows") or []:
        key, _ = _bucket_for_date(source.get("posting_date"), granularity)
        if key not in by_key:
            continue
        by_key[key]["money_in"] += flt(source.get("money_in"))
        by_key[key]["money_out"] += flt(source.get("money_out"))
    return {
        "description": _("Actual posted Cash and Bank movements for the selected period."),
        "chart_type": "grouped_bar",
        "currency": currency,
        "granularity": granularity,
        "series": [
            {"key": "money_in", "label": _("Money In"), "datatype": "Currency"},
            {"key": "money_out", "label": _("Money Out"), "datatype": "Currency"},
        ],
        "rows": rows,
        "route_filters": dict(filters),
    }


def _expense_visual(filters: dict[str, Any], *, currency: str) -> dict[str, Any]:
    dataset = get_expense_register_export(
        {
            **filters,
            "view_mode": "consolidated",
            "include_unposted_cashier_expenses": 0,
        }
    )
    buckets: dict[str, float] = defaultdict(float)
    for row in dataset.get("rows") or []:
        label = str(row.get("expense_category") or _("Unspecified")).strip() or _("Unspecified")
        buckets[label] += flt(row.get("amount"))
    return {
        "description": _("Largest posted expense categories in the selected period."),
        "chart_type": "bar",
        "currency": currency,
        "series": [{"key": "value", "label": _("Expenses"), "datatype": "Currency"}],
        "rows": _top_mix_rows(buckets),
        "route_filters": dict(filters),
    }


def _exposure_visual(filters: dict[str, Any], *, currency: str) -> dict[str, Any]:
    receivables = get_customer_receivables_export(filters)
    payables = get_supplier_payables_export(filters)
    receivable_buckets = defaultdict(float)
    payable_buckets = defaultdict(float)
    for row in receivables.get("rows") or []:
        receivable_buckets[str(row.get("ageing_bucket") or "Current")] += flt(
            row.get("outstanding")
        )
    for row in payables.get("rows") or []:
        payable_buckets[str(row.get("ageing_bucket") or "Current")] += flt(
            row.get("outstanding")
        )

    rows = [
        {
            "key": bucket,
            "label": bucket.replace(" Days", ""),
            "receivables": flt(receivable_buckets.get(bucket)),
            "payables": flt(payable_buckets.get(bucket)),
        }
        for bucket in AGE_BUCKETS
    ]
    return {
        "description": _("Current customer and supplier exposure by ageing bucket."),
        "chart_type": "grouped_bar",
        "currency": currency,
        "series": [
            {"key": "receivables", "label": _("Receivables"), "datatype": "Currency"},
            {"key": "payables", "label": _("Payables"), "datatype": "Currency"},
        ],
        "rows": rows,
        "route_filters": dict(filters),
        "secondary_route": "/app/supplier-payables",
    }


def _stock_health(filters: dict[str, Any]) -> dict[str, Any]:
    dataset = get_stock_position(filters=filters, page=1, page_size=1)
    summary = {
        str(row.get("label") or ""): flt(row.get("value"))
        for row in dataset.get("summary") or []
    }
    rows = [
        {"key": "available", "label": _("Available"), "value": summary.get("Available Items", 0)},
        {"key": "reorder_due", "label": _("Reorder Due"), "value": summary.get("Reorder Due", 0)},
        {"key": "out_of_stock", "label": _("Out of Stock"), "value": summary.get("Out of Stock", 0)},
        {"key": "negative", "label": _("Negative"), "value": summary.get("Negative Stock", 0)},
        {"key": "fully_reserved", "label": _("Fully Reserved"), "value": summary.get("Fully Reserved", 0)},
    ]
    return {
        "description": _("Current stock availability and replenishment exceptions."),
        "chart_type": "bar",
        "series": [{"key": "value", "label": _("Items"), "datatype": "Int"}],
        "rows": rows,
        "route_filters": dict(filters),
    }


def _granularity(start, end) -> str:
    days = (end - start).days + 1
    if days <= 31:
        return "day"
    if days <= 120:
        return "week"
    return "month"


def _bucket_for_date(value, granularity: str) -> tuple[str, str]:
    date = getdate(value)
    if granularity == "week":
        start = date - timedelta(days=date.weekday())
        return str(start), start.strftime("%d %b")
    if granularity == "month":
        start = date.replace(day=1)
        return str(start), start.strftime("%b %Y")
    return str(date), date.strftime("%d %b")


def _period_rows(start, end, granularity: str, metric_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    ordered: list[tuple[str, str]] = []
    seen: set[str] = set()
    cursor = start
    while cursor <= end:
        key, label = _bucket_for_date(cursor, granularity)
        if key not in seen:
            seen.add(key)
            ordered.append((key, label))
        cursor += timedelta(days=1)
    return [
        {"key": key, "label": label, **{metric: 0.0 for metric in metric_keys}}
        for key, label in ordered
    ]


def _top_mix_rows(buckets: dict[str, float]) -> list[dict[str, Any]]:
    ordered = sorted(
        ((label, flt(value)) for label, value in buckets.items()),
        key=lambda item: (-item[1], item[0]),
    )
    visible = ordered[:TOP_MIX_ROWS]
    remaining = ordered[TOP_MIX_ROWS:]
    rows = [{"key": label, "label": label, "value": value} for label, value in visible]
    if remaining:
        rows.append(
            {
                "key": "__other__",
                "label": _("Other"),
                "value": sum(value for _, value in remaining),
            }
        )
    return rows


def _unavailable_visuals(reason: str) -> list[dict[str, Any]]:
    definitions = (
        ("sales_trend", _("Sales Trend"), "/app/sales-invoice-register", "period"),
        ("sales_mix", _("Sales Mix"), "/app/sales-by-item", "period"),
        ("cash_flow", _("Cash In vs Cash Out"), "/app/cash-movement", "period"),
        ("expense_mix", _("Expense Mix"), "/app/expense-register", "period"),
        ("exposure", _("Receivables vs Payables"), "/app/customer-receivables", "current"),
        ("stock_health", _("Stock Health"), "/app/stock-position", "current"),
    )
    return [
        {
            "key": key,
            "title": title,
            "available": False,
            "route": route,
            "time_basis": time_basis,
            "reason": reason,
            "rows": [],
            "series": [],
        }
        for key, title, route, time_basis in definitions
    ]
