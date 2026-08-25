from __future__ import annotations

from typing import Any, Callable

import frappe

from retailedge.operating_context import get_operating_context
from retailedge.purchase_reporting import get_purchase_reporting_context as _base_purchase_reporting_context
from retailedge.sales_reporting import get_sales_reporting_context as _base_sales_reporting_context
from retailedge.stock_position import get_stock_position_context as _base_stock_position_context


def _company_currency(company: str) -> str:
	if not company:
		return ""
	try:
		return str(frappe.db.get_value("Company", company, "default_currency") or "")
	except Exception:
		return ""


def _with_operating_defaults(
	base_loader: Callable[[], dict[str, Any]],
	*,
	preserve_hidden_currency: bool = False,
) -> dict[str, Any]:
	"""Overlay Operating Company/Branch onto report *defaults* only.

	The returned filters remain ordinary editable report filters. This helper does
	not add permission filters, rewrite provider requests, persist user defaults, or
	prevent an authorized user from clearing/broadening Branch scope.
	"""
	context = dict(base_loader() or {})
	filters = dict(context.get("default_filters") or {})
	operating = get_operating_context()
	company = str(operating.get("company") or "").strip()
	branch = str(operating.get("branch") or "").strip()

	if company:
		filters["company"] = company
		context["tenant_name"] = company
		if not preserve_hidden_currency or context.get("show_costs", 1):
			context["company_currency"] = _company_currency(company)
	if branch:
		filters["branch"] = branch
		context["branch_name"] = branch
	elif company and filters.get("company") == company:
		# A company-only operating fallback should not carry a stale Branch default
		# from another user-default context.
		filters["branch"] = ""
		context["branch_name"] = ""

	# Warehouse is subordinate to Company/Branch. These context endpoints currently
	# default it empty; clearing defensively prevents future stale cross-context
	# defaults if a base report later adds one.
	if company or branch:
		filters["warehouse"] = ""

	context["default_filters"] = filters
	context["operating_context_defaulted"] = bool(company or branch)
	return context


@frappe.whitelist()
def get_sales_reporting_context() -> dict[str, Any]:
	return _with_operating_defaults(_base_sales_reporting_context)


@frappe.whitelist()
def get_purchase_reporting_context() -> dict[str, Any]:
	return _with_operating_defaults(_base_purchase_reporting_context)


@frappe.whitelist()
def get_stock_position_context() -> dict[str, Any]:
	return _with_operating_defaults(
		_base_stock_position_context,
		preserve_hidden_currency=True,
	)
