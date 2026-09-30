from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from retailedge.branch_context import BRANCH_FIELD_CANDIDATES, get_first_existing_field
from retailedge.operating_context import get_operational_branch_scope, validate_operating_branch

MAX_OPEN_DOCUMENT_ROWS = 2000


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _party_config(party_type: str) -> dict[str, str]:
	party_type = _clean(party_type)
	if party_type == "Customer":
		return {
			"party_type": "Customer",
			"party_field": "customer",
			"doctype": "Sales Invoice",
			"value_label": "Total Sales Value",
			"count_label": "Sales Invoices",
			"last_label": "Last Sale",
			"balance_label": "Current Balance",
			"source": "submitted ERPNext Sales Invoice",
		}
	if party_type == "Supplier":
		return {
			"party_type": "Supplier",
			"party_field": "supplier",
			"doctype": "Purchase Invoice",
			"value_label": "Total Purchase Value",
			"count_label": "Purchase Invoices",
			"last_label": "Last Purchase",
			"balance_label": "Current Balance",
			"source": "submitted ERPNext Purchase Invoice",
		}
	frappe.throw(_("Party Type must be Customer or Supplier."), frappe.ValidationError)


def _assert_named_read(doctype: str, name: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name or "(blank)"))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(
			_("You do not have permission to read {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)


def _branch_field(doctype: str) -> str | None:
	return get_first_existing_field(
		doctype,
		list(dict.fromkeys(["retailedge_branch", *BRANCH_FIELD_CANDIDATES])),
	)


def _resolve_scope(*, doctype: str, company: str, branch: str) -> tuple[str, str | None]:
	user = frappe.session.user
	scope = get_operational_branch_scope(company, user=user)
	allowed = sorted({_clean(value) for value in scope.get("allowed_branches") or [] if _clean(value)})
	branch = _clean(branch)

	if branch:
		validate_operating_branch(company=company, branch=branch, user=user, throw=True)
		if scope.get("restricted") and branch not in allowed:
			frappe.throw(
				_("You do not have active RetailEdge Branch access to Branch {0}.").format(branch),
				frappe.PermissionError,
			)
	elif scope.get("restricted"):
		if len(allowed) == 1:
			branch = allowed[0]
		else:
			frappe.throw(
				_("Choose an Operating Branch before loading party transaction context."),
				frappe.PermissionError,
			)

	fieldname = _branch_field(doctype)
	if branch and not fieldname:
		frappe.throw(
			_("{0} Branch attribution is unavailable; party transaction context cannot be scoped safely.").format(doctype),
			frappe.PermissionError,
		)
	return branch, fieldname


def _company_currency(company: str) -> str:
	return _clean(frappe.get_cached_value("Company", company, "default_currency"))


def _outstanding_is_company_currency(doctype: str) -> bool:
	field = frappe.get_meta(doctype).get_field("outstanding_amount")
	options = _clean(getattr(field, "options", ""))
	return options.startswith("Company:") or "company:default_currency" in options.lower()


def _summary(filters: dict[str, Any], doctype: str) -> dict[str, Any]:
	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=[
			"count(name) as document_count",
			"sum(base_net_total) as total_value",
			"max(posting_date) as last_transaction_date",
		],
		limit_page_length=1,
	)
	row = rows[0] if rows else frappe._dict()
	return {
		"document_count": cint(row.get("document_count")),
		"total_value": flt(row.get("total_value")),
		"last_transaction_date": row.get("last_transaction_date"),
	}


def _outstanding_summary(filters: dict[str, Any], doctype: str) -> dict[str, Any]:
	open_filters = {**filters, "outstanding_amount": ["!=", 0]}
	if _outstanding_is_company_currency(doctype):
		rows = frappe.get_list(
			doctype,
			filters=open_filters,
			fields=["sum(outstanding_amount) as current_balance", "count(name) as open_document_count"],
			limit_page_length=1,
		)
		overdue_filters = {**open_filters, "due_date": ["<", nowdate()]}
		overdue_rows = frappe.get_list(
			doctype,
			filters=overdue_filters,
			fields=["sum(outstanding_amount) as overdue_balance"],
			limit_page_length=1,
		)
		row = rows[0] if rows else frappe._dict()
		overdue = overdue_rows[0] if overdue_rows else frappe._dict()
		return {
			"current_balance": flt(row.get("current_balance")),
			"overdue_balance": flt(overdue.get("overdue_balance")),
			"open_document_count": cint(row.get("open_document_count")),
			"partial": False,
		}

	rows = frappe.get_list(
		doctype,
		filters=open_filters,
		fields=["name", "due_date", "outstanding_amount", "conversion_rate"],
		order_by="posting_date desc, name desc",
		limit_page_length=MAX_OPEN_DOCUMENT_ROWS + 1,
	)
	if len(rows) > MAX_OPEN_DOCUMENT_ROWS:
		return {
			"current_balance": None,
			"overdue_balance": None,
			"open_document_count": None,
			"partial": True,
		}

	current = 0.0
	overdue = 0.0
	today = nowdate()
	for row in rows:
		amount = flt(row.get("outstanding_amount")) * (flt(row.get("conversion_rate")) or 1.0)
		current += amount
		if row.get("due_date") and str(row.get("due_date")) < today:
			overdue += amount
	return {
		"current_balance": current,
		"overdue_balance": overdue,
		"open_document_count": len(rows),
		"partial": False,
	}


@frappe.whitelist()
def get_party_transaction_context(
	party_type: str,
	party: str,
	company: str,
	branch: str = "",
) -> dict[str, Any]:
	config = _party_config(party_type)
	party = _clean(party)
	company = _clean(company)
	branch = _clean(branch)
	if not party or not company:
		frappe.throw(_("Party and Company are required."), frappe.ValidationError)

	_assert_named_read("Company", company)
	_assert_named_read(config["party_type"], party)
	if not frappe.has_permission(config["doctype"], "read"):
		return {
			"available": False,
			"restricted": True,
			"party_type": config["party_type"],
			"party": party,
			"company": company,
			"branch": branch,
			"reason": _("Your current permissions do not allow invoice context for this party."),
			"metrics": [],
		}

	branch, branch_field = _resolve_scope(doctype=config["doctype"], company=company, branch=branch)
	filters: dict[str, Any] = {
		"docstatus": 1,
		"company": company,
		config["party_field"]: party,
	}
	if branch and branch_field:
		filters[branch_field] = branch

	transaction = _summary(filters, config["doctype"])
	outstanding = _outstanding_summary(filters, config["doctype"])
	currency = _company_currency(company)
	metrics = [
		{
			"key": "current_balance",
			"label": config["balance_label"],
			"value": outstanding["current_balance"],
			"datatype": "Currency",
			"currency": currency,
			"available": outstanding["current_balance"] is not None,
		},
		{
			"key": "overdue_balance",
			"label": "Overdue",
			"value": outstanding["overdue_balance"],
			"datatype": "Currency",
			"currency": currency,
			"available": outstanding["overdue_balance"] is not None,
		},
		{
			"key": "total_value",
			"label": config["value_label"],
			"value": transaction["total_value"],
			"datatype": "Currency",
			"currency": currency,
			"available": True,
		},
		{
			"key": "document_count",
			"label": config["count_label"],
			"value": transaction["document_count"],
			"datatype": "Int",
			"available": True,
		},
	]
	return {
		"available": True,
		"restricted": False,
		"partial": bool(outstanding["partial"]),
		"party_type": config["party_type"],
		"party": party,
		"company": company,
		"branch": branch,
		"currency": currency,
		"metrics": metrics,
		"open_document_count": outstanding["open_document_count"],
		"last_transaction_date": transaction["last_transaction_date"],
		"source_of_truth": config["source"],
		"helper": (
			_("Open-balance metrics are unavailable because more than {0} open documents require multi-currency conversion.").format(MAX_OPEN_DOCUMENT_ROWS)
			if outstanding["partial"]
			else _("Submitted ERPNext invoices; current balances use live outstanding amounts.")
		),
	}


__all__ = ["get_party_transaction_context"]
