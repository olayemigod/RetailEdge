from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe import _

from retailedge.branch_context import user_has_global_branch_access
from retailedge.branch_profile import get_user_branch_profiles
from retailedge.operating_context import get_operating_context
from retailedge.purchase_reporting import (
	get_purchase_register as _base_get_purchase_register,
	get_purchase_register_export as _base_get_purchase_register_export,
	get_purchase_reporting_context as _base_purchase_reporting_context,
	get_supplier_payables as _base_get_supplier_payables,
	get_supplier_payables_export as _base_get_supplier_payables_export,
	search_purchase_reporting_options as _base_search_purchase_reporting_options,
)
from retailedge.replenishment_handoff import (
	get_replenishment_handoff_context as _base_replenishment_handoff_context,
	get_replenishment_material_request_handoff as _base_replenishment_material_request_handoff,
)
from retailedge.sales_reporting import (
	get_sales_by_item as _base_get_sales_by_item,
	get_sales_by_item_export as _base_get_sales_by_item_export,
	get_sales_invoice_register as _base_get_sales_invoice_register,
	get_sales_invoice_register_export as _base_get_sales_invoice_register_export,
	get_sales_reporting_context as _base_sales_reporting_context,
	search_sales_reporting_options as _base_search_sales_reporting_options,
)
from retailedge.stock_position import (
	get_stock_position as _base_get_stock_position,
	get_stock_position_context as _base_stock_position_context,
	get_stock_position_export as _base_get_stock_position_export,
	search_stock_position_options as _base_search_stock_position_options,
)
from retailedge.supplier_payables import get_supplier_payables_export as _base_current_supplier_payables_export


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
	"""Overlay Operating Company/Branch onto editable initial report defaults."""
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
		filters["branch"] = ""
		context["branch_name"] = ""

	if company or branch:
		filters["warehouse"] = ""

	context["default_filters"] = filters
	context["operating_context_defaulted"] = bool(company or branch)
	return context


def _coerce_filters(filters: dict[str, Any] | str | None) -> dict[str, Any]:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return dict(filters or {})


def _assigned_profile_scope(company: str) -> tuple[bool, list[str]]:
	user = frappe.session.user
	company = str(company or "").strip()
	if not company or user_has_global_branch_access(user=user):
		return False, []
	try:
		rows = get_user_branch_profiles(user=user, company=company)
	except Exception:
		frappe.throw(
			_("Your assigned Branch reporting scope could not be verified. Try again or contact an administrator."),
			frappe.PermissionError,
		)
	if not rows:
		return False, []
	branches = sorted(
		{
			str(row.get("branch") or "").strip()
			for row in rows
			if row.get("enabled") and str(row.get("branch") or "").strip()
		}
	)
	if not branches:
		frappe.throw(
			_("You do not have an active Branch Setup assignment for this Company."),
			frappe.PermissionError,
		)
	return True, branches


def _constrain_report_filters(filters: dict[str, Any] | str | None) -> dict[str, Any]:
	resolved = _coerce_filters(filters)
	company = str(resolved.get("company") or "").strip()
	configured, assigned = _assigned_profile_scope(company)
	if not configured:
		return resolved

	branch = str(resolved.get("branch") or "").strip()
	if not branch:
		frappe.throw(
			_("Choose one of your assigned Branches. Cross-branch reporting is available only to authorized managers."),
			frappe.PermissionError,
		)
	if branch not in assigned:
		frappe.throw(_("You do not have reporting access to Branch {0}.").format(branch), frappe.PermissionError)
	return resolved


def _constrain_search_scope(kind: str, company: str, branch: str) -> tuple[str, list[str]]:
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	configured, assigned = _assigned_profile_scope(company)
	if not configured:
		return branch, []
	if branch and branch not in assigned:
		frappe.throw(_("You do not have reporting access to Branch {0}.").format(branch), frappe.PermissionError)
	if str(kind or "").strip().lower() == "warehouse" and not branch:
		return "", assigned
	return branch, assigned


def _filter_branch_options(options: list[dict[str, Any]], assigned: list[str]) -> list[dict[str, Any]]:
	if not assigned:
		return options
	allowed = set(assigned)
	return [row for row in options if str(row.get("value") or "") in allowed]


@frappe.whitelist()
def get_sales_reporting_context() -> dict[str, Any]:
	return _with_operating_defaults(_base_sales_reporting_context)


@frappe.whitelist()
def get_purchase_reporting_context() -> dict[str, Any]:
	return _with_operating_defaults(_base_purchase_reporting_context)


@frappe.whitelist()
def get_stock_position_context() -> dict[str, Any]:
	return _with_operating_defaults(_base_stock_position_context, preserve_hidden_currency=True)


@frappe.whitelist()
def get_replenishment_handoff_context() -> dict[str, int]:
	return _base_replenishment_handoff_context()


@frappe.whitelist()
def search_sales_reporting_options(kind: str, txt: str = "", company: str = "", branch: str = "", item_group: str = ""):
	branch, assigned = _constrain_search_scope(kind, company, branch)
	if str(kind or "").strip().lower() == "warehouse" and assigned and not branch:
		return []
	rows = _base_search_sales_reporting_options(kind=kind, txt=txt, company=company, branch=branch, item_group=item_group)
	return _filter_branch_options(rows, assigned) if str(kind or "").strip().lower() == "branch" else rows


@frappe.whitelist()
def search_purchase_reporting_options(kind: str, txt: str = "", company: str = "", branch: str = "", item_group: str = ""):
	branch, assigned = _constrain_search_scope(kind, company, branch)
	if str(kind or "").strip().lower() == "warehouse" and assigned and not branch:
		return []
	rows = _base_search_purchase_reporting_options(kind=kind, txt=txt, company=company, branch=branch, item_group=item_group)
	return _filter_branch_options(rows, assigned) if str(kind or "").strip().lower() == "branch" else rows


@frappe.whitelist()
def search_stock_position_options(kind: str, txt: str = "", company: str = "", branch: str = "", item_group: str = ""):
	branch, assigned = _constrain_search_scope(kind, company, branch)
	if str(kind or "").strip().lower() == "warehouse" and assigned and not branch:
		return []
	rows = _base_search_stock_position_options(kind=kind, txt=txt, company=company, branch=branch, item_group=item_group)
	return _filter_branch_options(rows, assigned) if str(kind or "").strip().lower() == "branch" else rows


@frappe.whitelist()
def get_sales_by_item(filters=None, page=1, page_size=50):
	return _base_get_sales_by_item(filters=_constrain_report_filters(filters), page=page, page_size=page_size)


@frappe.whitelist()
def get_sales_by_item_export(filters=None):
	return _base_get_sales_by_item_export(filters=_constrain_report_filters(filters))


@frappe.whitelist()
def get_sales_invoice_register(filters=None, page=1, page_size=50):
	return _base_get_sales_invoice_register(filters=_constrain_report_filters(filters), page=page, page_size=page_size)


@frappe.whitelist()
def get_sales_invoice_register_export(filters=None):
	return _base_get_sales_invoice_register_export(filters=_constrain_report_filters(filters))


@frappe.whitelist()
def get_purchase_register(filters=None, page=1, page_size=50):
	return _base_get_purchase_register(filters=_constrain_report_filters(filters), page=page, page_size=page_size)


@frappe.whitelist()
def get_purchase_register_export(filters=None):
	return _base_get_purchase_register_export(filters=_constrain_report_filters(filters))


@frappe.whitelist()
def get_supplier_payables(filters=None, page=1, page_size=50):
	return _base_get_supplier_payables(filters=_constrain_report_filters(filters), page=page, page_size=page_size)


@frappe.whitelist()
def get_supplier_payables_export(filters=None):
	return _base_get_supplier_payables_export(filters=_constrain_report_filters(filters))


def get_governed_supplier_payables_export(filters=None):
	"""Preserve the dedicated current-outstanding Supplier Payables export contract."""
	return _base_current_supplier_payables_export(filters=_constrain_report_filters(filters))


@frappe.whitelist()
def get_stock_position(filters=None, page=1, page_size=50):
	return _base_get_stock_position(filters=_constrain_report_filters(filters), page=page, page_size=page_size)


@frappe.whitelist()
def get_stock_position_export(filters=None):
	return _base_get_stock_position_export(filters=_constrain_report_filters(filters))


@frappe.whitelist(methods=["POST"])
def get_replenishment_material_request_handoff(item_code: str, filters=None):
	return _base_replenishment_material_request_handoff(
		item_code=item_code,
		filters=_constrain_report_filters(filters),
	)
