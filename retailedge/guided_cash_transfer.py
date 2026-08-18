from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from retailedge.branch_context import (
	get_user_allowed_branches,
	has_doctype,
	has_field,
	resolve_retailedge_operational_defaults,
	user_has_global_branch_access,
	validate_user_branch_access,
)

PAYMENT_ENTRY_DOCTYPE = "Payment Entry"
MAX_LINK_RESULTS = 20


@frappe.whitelist()
def get_simple_cash_transfer_context() -> dict[str, Any]:
	_assert_can_create_payment_entry()
	user = frappe.session.user
	company = frappe.defaults.get_user_default("Company") or ""
	branch = (
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	)
	defaults = resolve_retailedge_operational_defaults(
		company=company or None,
		branch=branch or None,
		user=user,
	)
	company = defaults.get("company") or company
	branch = defaults.get("branch") or branch
	if not company:
		frappe.throw(_("Set a default Company before recording a Cash/Bank Transfer."))
	_assert_read_permission("Company", company)
	if branch:
		validate_user_branch_access(branch, user=user, company=company, throw=True)

	return {
		"title": _("Cash / Bank Transfer"),
		"subtitle": _(
			"Create a standard ERPNext Payment Entry draft for an internal transfer between permitted Cash or Bank accounts."
		),
		"submit_label": _("Save Draft"),
		"full_form_doctype": PAYMENT_ENTRY_DOCTYPE,
		"defaults": {
			"company": company,
			"branch": branch or "",
			"posting_date": nowdate(),
			"from_account": "",
			"to_account": "",
			"amount": "",
			"reference_no": "",
			"reference_date": nowdate(),
			"remarks": "",
		},
		"capabilities": {
			"branch_enabled": bool(has_doctype("Branch")),
			"native_form_fallback": True,
		},
		"limits": {"link_results": MAX_LINK_RESULTS},
	}


@frappe.whitelist()
def search_simple_cash_transfer_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_can_create_payment_entry()
	values = _coerce_values(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	company = str(values.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if fieldname in {"from_account", "to_account"}:
		return _search_bank_cash_accounts(company=company, txt=txt or "", limit=limit)
	if fieldname == "branch":
		return _search_branches(company=company, txt=txt or "", limit=limit)
	frappe.throw(_("Unsupported Cash / Bank Transfer search field: {0}").format(fieldname))
	return []


@frappe.whitelist(methods=["POST"])
def create_simple_cash_transfer_draft(values: dict | str | None = None) -> dict[str, Any]:
	_assert_can_create_payment_entry()
	values = _coerce_values(values)
	user = frappe.session.user
	company = str(values.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	_assert_read_permission("Company", company)
	company_currency = frappe.db.get_value("Company", company, "default_currency")
	if not company_currency:
		frappe.throw(_("Company {0} has no default currency configured.").format(company))

	branch = str(values.get("branch") or "").strip()
	if branch:
		validate_user_branch_access(branch, user=user, company=company, throw=True)

	from_account = str(values.get("from_account") or "").strip()
	to_account = str(values.get("to_account") or "").strip()
	if not from_account or not to_account:
		frappe.throw(_("From Account and To Account are required."))
	if from_account == to_account:
		frappe.throw(_("From Account and To Account must be different."))

	from_details = _get_transfer_account(company, from_account)
	to_details = _get_transfer_account(company, to_account)
	if from_details["account_currency"] != company_currency or to_details["account_currency"] != company_currency:
		frappe.throw(
			_(
				"Simple Cash / Bank Transfer currently supports company-currency accounts only. Use the full Payment Entry form for multi-currency transfers."
			)
		)

	amount = flt(values.get("amount"))
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero."))
	posting_date = getdate(values.get("posting_date") or nowdate())

	doc = frappe.new_doc(PAYMENT_ENTRY_DOCTYPE)
	doc.payment_type = "Internal Transfer"
	doc.company = company
	doc.posting_date = posting_date
	doc.paid_from = from_account
	doc.paid_to = to_account
	doc.paid_amount = amount
	doc.received_amount = amount

	if branch:
		if has_field(PAYMENT_ENTRY_DOCTYPE, "retailedge_branch"):
			doc.retailedge_branch = branch
		elif has_field(PAYMENT_ENTRY_DOCTYPE, "branch"):
			doc.branch = branch

	if from_details["account_type"] == "Bank" or to_details["account_type"] == "Bank":
		reference_no = str(values.get("reference_no") or "").strip()
		if not reference_no:
			frappe.throw(_("Reference No is required when a Bank account is involved."))
		doc.reference_no = reference_no
		doc.reference_date = getdate(values.get("reference_date") or posting_date)

	remarks = str(values.get("remarks") or "").strip()
	if remarks:
		doc.custom_remarks = 1
		doc.remarks = remarks

	# Insert as the current user and keep the transaction in Draft. ERPNext Payment Entry
	# validation remains authoritative for account, currency, exchange-rate and ledger safety.
	doc.insert()
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"payment_type": doc.payment_type,
		"company": doc.company,
		"branch": branch,
		"from_account": doc.paid_from,
		"to_account": doc.paid_to,
		"amount": doc.paid_amount,
		"route": f"/app/payment-entry/{doc.name}",
	}


def _search_bank_cash_accounts(*, company: str, txt: str, limit: int) -> list[dict[str, Any]]:
	if not company:
		return []
	_assert_read_permission("Company", company)
	filters: dict[str, Any] = {
		"company": company,
		"is_group": 0,
		"account_type": ["in", ["Bank", "Cash"]],
	}
	if has_field("Account", "disabled"):
		filters["disabled"] = 0
	if txt:
		filters["name"] = ["like", f"%{txt}%"]
	rows = frappe.get_list(
		"Account",
		filters=filters,
		fields=["name", "account_name", "account_type", "account_currency"],
		order_by="account_type asc, account_name asc, name asc",
		limit_page_length=limit,
	)
	return [
		{
			"value": row.name,
			"label": row.account_name or row.name,
			"description": _("{0} · {1}").format(row.account_type, row.account_currency or ""),
		}
		for row in rows
	]


def _search_branches(*, company: str, txt: str, limit: int) -> list[dict[str, Any]]:
	if not has_doctype("Branch"):
		return []
	filters: dict[str, Any] = {}
	if company and has_field("Branch", "company"):
		filters["company"] = company
	if not user_has_global_branch_access(user=frappe.session.user):
		allowed = get_user_allowed_branches(user=frappe.session.user, company=company or None).get("branches") or []
		if not allowed:
			return []
		filters["name"] = ["in", allowed]
	if txt:
		filters["name"] = ["like", f"%{txt}%"] if "name" not in filters else ["in", [name for name in filters["name"][1] if txt.lower() in name.lower()]]
	rows = frappe.get_list(
		"Branch",
		filters=filters,
		fields=["name"],
		order_by="name asc",
		limit_page_length=limit,
	)
	return [{"value": row.name, "label": row.name} for row in rows]


def _get_transfer_account(company: str, account: str) -> dict[str, Any]:
	_assert_read_permission("Account", account)
	fields = ["company", "is_group", "account_type", "account_currency"]
	if has_field("Account", "disabled"):
		fields.append("disabled")
	row = frappe.db.get_value("Account", account, fields, as_dict=True)
	if not row or row.company != company or cint(row.is_group):
		frappe.throw(_("Account {0} is not a posting account for Company {1}.").format(account, company))
	if row.account_type not in {"Bank", "Cash"}:
		frappe.throw(_("Account {0} must be a Bank or Cash account.").format(account))
	if cint(row.get("disabled")):
		frappe.throw(_("Account {0} is disabled.").format(account))
	return {
		"account_type": row.account_type,
		"account_currency": row.account_currency,
	}


def _assert_can_create_payment_entry() -> None:
	if not has_doctype(PAYMENT_ENTRY_DOCTYPE) or not frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Payment Entries."), frappe.PermissionError)


def _assert_read_permission(doctype: str, name: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to use {0} {1}.").format(doctype, name), frappe.PermissionError)


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if not values:
		return {}
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if isinstance(values, frappe._dict):
		return dict(values)
	if isinstance(values, dict):
		return values
	frappe.throw(_("Cash / Bank Transfer values must be a mapping."))
	return {}
