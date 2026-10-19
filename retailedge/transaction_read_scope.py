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
	"""Return only an explicit session-selected RetailEdge working scope."""
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
	if not pairs or not _meta_has_field(doctype, BRANCH_FIELD):
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


def _permission_query_conditions(doctype: str, user: str | None = None) -> str:
	"""Compose RetailEdge branch scope with Frappe's native permission query."""
	user = user or frappe.session.user
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
		return ""
	return _sql_company_branch_scope(doctype, _active_assignment_pairs(user))


# Frappe v16 passes both user and doctype keyword arguments to query hooks.
# Concrete wrappers keep the target table explicit while accepting that native
# signature for upgrade safety.
def get_quotation_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Quotation", user)


def get_sales_order_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Sales Order", user)


def get_delivery_note_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Delivery Note", user)


def get_sales_invoice_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Sales Invoice", user)


def get_pos_invoice_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("POS Invoice", user)


def get_purchase_order_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Purchase Order", user)


def get_purchase_receipt_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Purchase Receipt", user)


def get_purchase_invoice_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Purchase Invoice", user)


def get_supplier_quotation_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Supplier Quotation", user)


def get_request_for_quotation_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Request for Quotation", user)


def get_payment_entry_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Payment Entry", user)


def get_payment_request_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Payment Request", user)


def get_material_request_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Material Request", user)


def get_stock_entry_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Stock Entry", user)


def get_stock_reconciliation_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	return _permission_query_conditions("Stock Reconciliation", user)


def has_permission(doc, ptype: str | None = None, user: str | None = None, debug: bool = False):
	"""Keep direct document access aligned with the branch query condition.

	Frappe v16 requires an explicit True from an applicable has_permission hook.
	That True cannot grant access when native role permissions already deny it;
	False removes access when Company/Branch scope is violated.
	"""
	user = user or frappe.session.user
	ptype = ptype or "read"
	doctype = _clean(getattr(doc, "doctype", None))
	if doctype not in BRANCH_SCOPED_TRANSACTION_DOCTYPES:
		return True
	if ptype == "create" or bool(getattr(doc, "is_new", lambda: False)()):
		return True

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
		return True
	if not has_branch_assignments(user=user):
		return True
	if not company or not branch:
		return False
	return (company, branch) in set(_active_assignment_pairs(user))
