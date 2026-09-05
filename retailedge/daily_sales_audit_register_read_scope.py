from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.daily_sales_audit_read_scope import apply_daily_sales_audit_query_branch_scope

DAILY_SALES_AUDIT_DOCTYPE = "RetailEdge Daily Sales Audit"
REGISTER_BUSINESS_FILTERS = (
	"pos_profile",
	"cashier",
	"audit_status",
	"audit_result",
)


def resolve_daily_sales_audit_register_read_scope(
	filters: dict[str, Any] | None,
	*,
	user: str | None = None,
) -> dict[str, Any]:
	"""Return authoritative Company/Branch predicates plus scalar register filters."""
	filters = dict(filters or {})
	company = _clean_scalar(filters.get("company"), fieldname="Company")
	if not company:
		frappe.throw(_("Company is required."), frappe.ValidationError)

	_assert_daily_sales_audit_read_access()
	_assert_company_read_access(company)
	reader = user or getattr(getattr(frappe, "session", None), "user", "Administrator")
	branch = _clean_scalar(filters.get("branch"), fieldname="Branch")
	selection = {"company": company}
	if branch:
		selection["branch"] = branch
	branch_scope = apply_daily_sales_audit_query_branch_scope(
		DAILY_SALES_AUDIT_DOCTYPE,
		selection,
		branch_field="branch",
		user=reader,
	)
	if branch_scope is None:
		frappe.throw(
			_("Daily Sales Audit Register Branch scope could not be resolved."), frappe.PermissionError
		)

	query_filters: dict[str, Any] = {"company": company, **branch_scope}
	for fieldname in REGISTER_BUSINESS_FILTERS:
		value = _clean_scalar(filters.get(fieldname), fieldname=fieldname.replace("_", " ").title())
		if value:
			query_filters[fieldname] = value
	return query_filters


def _assert_daily_sales_audit_read_access() -> None:
	if not frappe.db.exists("DocType", DAILY_SALES_AUDIT_DOCTYPE) or not frappe.has_permission(
		DAILY_SALES_AUDIT_DOCTYPE, "read"
	):
		frappe.throw(
			_("You do not have permission to view Daily Sales Audit records."),
			frappe.PermissionError,
		)


def _assert_company_read_access(company: str) -> None:
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(
			_("You do not have permission to use Company {0}.").format(company),
			frappe.PermissionError,
		)


def _clean_scalar(value: Any, *, fieldname: str) -> str:
	if value in (None, ""):
		return ""
	if isinstance(value, (list, tuple, dict, set)):
		frappe.throw(
			_("Daily Sales Audit Register {0} must be a single value.").format(fieldname),
			frappe.ValidationError,
		)
	return str(value).strip()
