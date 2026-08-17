from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr

from retailedge.reporting_capabilities import require_report_action


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})


def _export_handler(report_key: str) -> Callable[..., dict[str, Any]]:
	key = cstr(report_key or "").strip().lower()
	if key == "sales-by-item":
		from retailedge.sales_reporting import get_sales_by_item_export

		return get_sales_by_item_export
	if key == "sales-invoice-register":
		from retailedge.sales_reporting import get_sales_invoice_register_export

		return get_sales_invoice_register_export
	if key == "stock-position":
		from retailedge.stock_position import get_stock_position_export

		return get_stock_position_export
	if key == "stock-movement-history":
		from retailedge.stock_movement_page import get_stock_movement_export

		return get_stock_movement_export
	if key == "expense-register":
		from retailedge.expense_register import get_expense_register_export

		return get_expense_register_export
	if key == "cash-movement":
		from retailedge.cash_movement import get_cash_movement_export

		return get_cash_movement_export
	frappe.throw(_("Unsupported RetailEdge report export scope."))


@frappe.whitelist()
def get_report_export_data(
	report_key: str,
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	"""Return a permission-checked bounded export dataset for one RetailEdge report.

	The report's existing backend remains authoritative for row-level permissions,
	company/branch scoping, cost visibility and safety caps. This wrapper adds the
	independent bulk-export authorization required by the EdgeSuite shell contract.
	"""
	resolved_filters = _coerce_filters(filters)
	company = cstr(resolved_filters.get("company") or "").strip()
	branch = cstr(resolved_filters.get("branch") or "").strip()
	require_report_action(
		report_key,
		action="export",
		company=company,
		branch=branch,
	)
	handler = _export_handler(report_key)
	return handler(filters=resolved_filters)


@frappe.whitelist()
def get_report_print_capabilities(
	report_key: str,
	company: str = "",
	branch: str = "",
) -> dict[str, object]:
	"""Revalidate print authorization immediately before a print workflow starts."""
	return require_report_action(
		report_key,
		action="print",
		company=company,
		branch=branch,
	)
