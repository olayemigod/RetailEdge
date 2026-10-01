from __future__ import annotations

import frappe

from retailedge.reporting_scope import get_report_branch_scope


READ_ROLES = {
	"System Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}
_READ_PERMISSION_TYPES = {None, "read", "report", "export", "print", "email"}


def get_operation_permission_query_conditions(user: str | None = None) -> str:
	return _permission_query_conditions(
		"RetailEdge CoreEdge Quota Operation",
		user=user,
	)


def get_review_event_permission_query_conditions(user: str | None = None) -> str:
	return _permission_query_conditions(
		"RetailEdge CoreEdge Quota Review Event",
		user=user,
	)


def has_operation_permission(
	doc,
	user: str | None = None,
	permission_type: str | None = None,
) -> bool:
	return _has_scoped_permission(doc, user=user, permission_type=permission_type)


def has_review_event_permission(
	doc,
	user: str | None = None,
	permission_type: str | None = None,
) -> bool:
	return _has_scoped_permission(doc, user=user, permission_type=permission_type)


def _permission_query_conditions(doctype: str, *, user: str | None = None) -> str:
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	if not set(frappe.get_roles(user)).intersection(READ_ROLES):
		return "1=0"

	clauses: list[str] = []
	for company in _readable_companies(user):
		try:
			scope = get_report_branch_scope(company, user=user)
		except (frappe.PermissionError, frappe.ValidationError):
			continue

		company_sql = (
			f"`tab{doctype}`.`company` = {frappe.db.escape(company)}"
		)
		if not scope.get("restricted"):
			clauses.append(f"({company_sql})")
			continue

		allowed = [
			str(value).strip()
			for value in dict.fromkeys(scope.get("allowed_branches") or [])
			if str(value or "").strip()
		]
		for branch in allowed:
			branch_sql = (
				f"`tab{doctype}`.`branch` = {frappe.db.escape(branch)}"
			)
			clauses.append(f"({company_sql} AND {branch_sql})")

	return f"({' OR '.join(clauses)})" if clauses else "1=0"


def _has_scoped_permission(
	doc,
	*,
	user: str | None = None,
	permission_type: str | None = None,
) -> bool:
	user = user or frappe.session.user
	if permission_type not in _READ_PERMISSION_TYPES:
		return False
	if user == "Administrator":
		return True
	if not set(frappe.get_roles(user)).intersection(READ_ROLES):
		return False

	company = str(getattr(doc, "company", None) or "").strip()
	branch = str(getattr(doc, "branch", None) or "").strip()
	if not company or not frappe.has_permission("Company", "read", doc=company, user=user):
		return False

	try:
		scope = get_report_branch_scope(company, user=user)
	except (frappe.PermissionError, frappe.ValidationError):
		return False
	if not scope.get("restricted"):
		return True

	allowed = {
		str(value).strip()
		for value in scope.get("allowed_branches") or []
		if str(value or "").strip()
	}
	return bool(branch and branch in allowed)


def _readable_companies(user: str) -> list[str]:
	companies = frappe.get_all("Company", pluck="name", limit_page_length=0)
	return [
		company
		for company in companies
		if frappe.has_permission("Company", "read", doc=company, user=user)
	]
