from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe

from retailedge.branch_assignment import get_active_branch_assignments, has_branch_assignments
from retailedge.branch_context import user_has_global_branch_access
from retailedge.operating_context import get_operating_context


BRANCH_SCOPED_TRANSACTION_DOCTYPES = {
	"Quotation",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"POS Invoice",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Supplier Quotation",
	"Request for Quotation",
	"Payment Entry",
	"Payment Request",
	"Material Request",
	"Stock Entry",
	"Stock Reconciliation",
}
BRANCH_FIELD = "retailedge_branch"
COMPANY_FIELD = "company"


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _meta_has_field(doctype: str, fieldname: str) -> bool:
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def _active_assignment_pairs(user: str) -> list[tuple[str, str]]:
	pairs: list[tuple[str, str]] = []
	for row in get_active_branch_assignments(user=user):
		company = _clean(row.get("company"))
		branch = _clean(row.get("branch"))
		if company and branch and (company, branch) not in pairs:
			pairs.append((company, branch))
	return pairs


def _explicit_working_scope(user: str) -> dict[str, Any]:
	"""Return only an explicit session-selected RetailEdge working scope.

	Fallback/default context must not silently narrow native ERPNext users. A
	server-enforced read scope starts only after the user deliberately switches
	Working Branch or chooses All Branches.
	"""
	try:
		context = get_operating_context() or {}
	except Exception:
		return {}
	if _clean(context.get("source")) != "session":
		return {}
	company = _clean(context.get("company"))
	branch = _clean(context.get("branch"))
	if not company:
		return {}
	return {
		"company": company,
		"branch": branch,
		"company_wide": bool(context.get("company_wide")),
	}


def _sql_company_branch_scope(doctype: str, pairs: list[tuple[str, str]]) -> str:
	if not pairs:
		return "1=0"
	if not _meta_has_field(doctype, BRANCH_FIELD):
		return "1=0"

	table = f"`tab{doctype}`"
	if not _meta_has_field(doctype, COMPANY_FIELD):
		branches = list(dict.fromkeys(branch for _company, branch in pairs))
		branch_sql = ", ".join(frappe.db.escape(branch) for branch in branches)
		return f"{table}.`{BRANCH_FIELD}` in ({branch_sql})" if branch_sql else "1=0"

	grouped: dict[str, list[str]] = defaultdict(list)
	for company, branch in pairs:
		if branch not in grouped[company]:
			grouped[company].append(branch)

	clauses = []
	for company, branches in grouped.items():
		branch_sql = ", ".join(frappe.db.escape(branch) for branch in branches)
		if not branch_sql:
			continue
		clauses.append(
			f"({table}.`{COMPANY_FIELD}` = {frappe.db.escape(company)} "
			f"and {table}.`{BRANCH_FIELD}` in ({branch_sql}))"
		)
	return f"({' or '.join(clauses)})" if clauses else "1=0"


def get_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	"""Compose Working Branch and Branch Assignment scope with native permissions.

	Frappe still applies Role Permission Manager, If Owner, User Permission and
	document sharing rules. This hook only narrows branch/company visibility.
	"""
	user = user or frappe.session.user
	doctype = _clean(doctype)
	if doctype not in BRANCH_SCOPED_TRANSACTION_DOCTYPES:
		return ""

	explicit = _explicit_working_scope(user)
	if explicit:
		company = explicit["company"]
		branch = explicit["branch"]
		if explicit["company_wide"]:
			if not _meta_has_field(doctype, COMPANY_FIELD):
				return "1=0"
			return f"`tab{doctype}`.`{COMPANY_FIELD}` = {frappe.db.escape(company)}"
		if not branch:
			return "1=0"
		return _sql_company_branch_scope(doctype, [(company, branch)])

	if user_has_global_branch_access(user=user):
		return ""
	if not has_branch_assignments(user=user):
		# Preserve native ERPNext/User Permission behavior for sites/users that
		# have not adopted RetailEdge Branch Assignment governance.
		return ""
	return _sql_company_branch_scope(doctype, _active_assignment_pairs(user))


def has_permission(
	doc,
	user: str | None = None,
	permission_type: str | None = None,
	ptype: str | None = None,
	debug: bool = False,
):
	"""Keep direct document access consistent with list/query branch scope.

	Returning True here cannot grant rights denied by native Frappe permissions;
	it only confirms the RetailEdge branch boundary. Returning None delegates the
	decision entirely to native permissions.
	"""
	user = user or frappe.session.user
	permission_type = permission_type or ptype or "read"
	doctype = _clean(getattr(doc, "doctype", None))
	if doctype not in BRANCH_SCOPED_TRANSACTION_DOCTYPES:
		return None
	if permission_type == "create" or bool(getattr(doc, "is_new", lambda: False)()):
		return None

	company = _clean(getattr(doc, COMPANY_FIELD, None))
	branch = _clean(getattr(doc, BRANCH_FIELD, None))
	explicit = _explicit_working_scope(user)
	if explicit:
		if company != explicit["company"]:
			return False
		if explicit["company_wide"]:
			return True
		return bool(branch and branch == explicit["branch"])

	if user_has_global_branch_access(user=user):
		return None
	if not has_branch_assignments(user=user):
		return None
	if not company or not branch:
		return False
	return (company, branch) in set(_active_assignment_pairs(user))
