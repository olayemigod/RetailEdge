from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, flt, getdate, nowdate

from retailedge.branch_context import has_doctype, has_field, validate_user_branch_access
from retailedge.cashier_context import get_current_cashier_context, get_shift_cash_snapshot

PAYMENT_ENTRY_DOCTYPE = "Payment Entry"
CASH_DEPOSIT_TYPE = "Cash Deposit"
MAX_LINK_RESULTS = 20

CUSTODY_FIELD_DEFS = {
	"retailedge_cash_custody_type": {
		"label": "RetailEdge Cash Custody Type",
		"fieldtype": "Select",
		"options": "\nCash Deposit",
		"read_only": 1,
		"hidden": 1,
	},
	"retailedge_cashier": {
		"label": "RetailEdge Cashier",
		"fieldtype": "Link",
		"options": "User",
		"read_only": 1,
		"hidden": 1,
	},
	"retailedge_pos_opening_shift": {
		"label": "RetailEdge POS Opening Shift",
		"fieldtype": "Data",
		"read_only": 1,
		"hidden": 1,
	},
}


def ensure_cash_custody_custom_fields():
	"""Idempotently add the minimal Payment Entry metadata needed for cash custody."""
	if not has_doctype(PAYMENT_ENTRY_DOCTYPE):
		return {}
	insert_after = "retailedge_branch" if has_field(PAYMENT_ENTRY_DOCTYPE, "retailedge_branch") else "remarks"
	field_defs = []
	for fieldname, definition in CUSTODY_FIELD_DEFS.items():
		field_defs.append({"fieldname": fieldname, "insert_after": insert_after, **definition})
		insert_after = fieldname
	custom_fields = {PAYMENT_ENTRY_DOCTYPE: field_defs}
	create_custom_fields(custom_fields, ignore_validate=True, update=True)
	return custom_fields


@frappe.whitelist()
def get_cash_deposit_context() -> dict[str, Any]:
	_assert_can_create_payment_entry()
	ensure_cash_custody_custom_fields()
	context = get_current_cashier_context(user=frappe.session.user)
	shift = str(context.get("linked_pos_opening_shift") or "").strip()
	if not shift:
		frappe.throw(_("Open a POS shift before depositing cashier cash."))
	company = str(context.get("company") or "").strip()
	branch = str(context.get("branch") or "").strip()
	cash_account = str(context.get("payment_account") or "").strip()
	if not company or not cash_account:
		frappe.throw(_("RetailEdge could not resolve the active shift company and cash account."))
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)
	_snapshot = get_cash_custody_snapshot(
		opening_shift=shift,
		company=company,
		pos_profile=context.get("pos_profile"),
		cashier=frappe.session.user,
	)
	return {
		"title": _("Deposit Cash"),
		"subtitle": _("Move accountable cashier cash to a bank account using a standard ERPNext Payment Entry."),
		"submit_label": _("Save Draft"),
		"full_form_doctype": PAYMENT_ENTRY_DOCTYPE,
		"defaults": {
			"company": company,
			"branch": branch,
			"cashier": frappe.session.user,
			"pos_opening_shift": shift,
			"posting_date": nowdate(),
			"from_account": cash_account,
			"to_account": "",
			"amount": "",
			"reference_no": "",
			"reference_date": nowdate(),
			"remarks": "",
		},
		"custody": _snapshot,
		"limits": {"link_results": MAX_LINK_RESULTS},
	}


@frappe.whitelist()
def search_cash_deposit_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_can_create_payment_entry()
	values = _coerce_values(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	company = str(values.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if fieldname != "to_account":
		frappe.throw(_("Unsupported Deposit Cash search field: {0}").format(fieldname))
	if not company:
		return []
	filters: dict[str, Any] = {"company": company, "is_group": 0, "account_type": "Bank"}
	if has_field("Account", "disabled"):
		filters["disabled"] = 0
	if txt:
		filters["name"] = ["like", f"%{txt}%"]
	rows = frappe.get_list(
		"Account",
		filters=filters,
		fields=["name", "account_name", "account_currency"],
		order_by="account_name asc, name asc",
		limit_page_length=limit,
	)
	return [
		{
			"value": row.name,
			"label": row.account_name or row.name,
			"description": row.account_currency or "",
		}
		for row in rows
	]


@frappe.whitelist(methods=["POST"])
def create_cash_deposit_draft(values: dict | str | None = None) -> dict[str, Any]:
	_assert_can_create_payment_entry()
	ensure_cash_custody_custom_fields()
	values = _coerce_values(values)
	context = get_current_cashier_context(user=frappe.session.user)
	company = str(context.get("company") or "").strip()
	branch = str(context.get("branch") or "").strip()
	opening_shift = str(context.get("linked_pos_opening_shift") or "").strip()
	from_account = str(context.get("payment_account") or "").strip()
	if not company or not opening_shift or not from_account:
		frappe.throw(_("An open POS shift with a resolved cash account is required before depositing cash."))
	if values.get("company") and str(values.get("company")).strip() != company:
		frappe.throw(_("The selected company no longer matches the active cashier shift. Refresh Deposit Cash."))
	if values.get("from_account") and str(values.get("from_account")).strip() != from_account:
		frappe.throw(_("The source cash account is controlled by the active cashier shift and cannot be changed."))
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)

	from_details = _get_account(company, from_account, expected_type="Cash")
	to_account = str(values.get("to_account") or "").strip()
	if not to_account:
		frappe.throw(_("Bank Account is required."))
	to_details = _get_account(company, to_account, expected_type="Bank")
	company_currency = frappe.db.get_value("Company", company, "default_currency")
	if not company_currency:
		frappe.throw(_("Company {0} has no default currency configured.").format(company))
	if from_details["account_currency"] != company_currency or to_details["account_currency"] != company_currency:
		frappe.throw(_("Deposit Cash currently supports company-currency accounts only. Use the full Payment Entry form for multi-currency transfers."))

	amount = flt(values.get("amount"))
	if amount <= 0:
		frappe.throw(_("Deposit amount must be greater than zero."))
	custody = get_cash_custody_snapshot(
		opening_shift=opening_shift,
		company=company,
		pos_profile=context.get("pos_profile"),
		cashier=frappe.session.user,
	)
	if amount > flt(custody.get("available_cash")):
		frappe.throw(
			_("Deposit amount {0} exceeds available shift cash {1}.").format(
				frappe.format_value(amount, {"fieldtype": "Currency"}),
				frappe.format_value(custody.get("available_cash"), {"fieldtype": "Currency"}),
			)
		)

	posting_date = getdate(values.get("posting_date") or nowdate())
	doc = frappe.new_doc(PAYMENT_ENTRY_DOCTYPE)
	doc.payment_type = "Internal Transfer"
	doc.company = company
	doc.posting_date = posting_date
	doc.paid_from = from_account
	doc.paid_to = to_account
	doc.paid_amount = amount
	doc.received_amount = amount
	_set_if_field(doc, "retailedge_branch", branch)
	_set_if_field(doc, "retailedge_cash_custody_type", CASH_DEPOSIT_TYPE)
	_set_if_field(doc, "retailedge_cashier", frappe.session.user)
	_set_if_field(doc, "retailedge_pos_opening_shift", opening_shift)

	reference_no = str(values.get("reference_no") or "").strip()
	if not reference_no:
		frappe.throw(_("Reference No is required for a bank deposit."))
	doc.reference_no = reference_no
	doc.reference_date = getdate(values.get("reference_date") or posting_date)
	remarks = str(values.get("remarks") or "").strip()
	if remarks:
		doc.custom_remarks = 1
		doc.remarks = remarks

	# Keep accounting truth in ERPNext and deliberately save only a draft here.
	doc.insert()
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"payment_type": doc.payment_type,
		"company": doc.company,
		"branch": branch,
		"cashier": frappe.session.user,
		"pos_opening_shift": opening_shift,
		"from_account": doc.paid_from,
		"to_account": doc.paid_to,
		"amount": doc.paid_amount,
		"available_cash_before_draft": custody.get("available_cash"),
		"route": f"/app/payment-entry/{doc.name}",
	}


def get_cash_custody_snapshot(
	*,
	opening_shift: str,
	company: str | None = None,
	pos_profile: str | None = None,
	cashier: str | None = None,
	exclude_payment_entry: str | None = None,
) -> dict[str, Any]:
	"""Return shift cash after recognised expenses and submitted deposits only."""
	base = get_shift_cash_snapshot(
		opening_shift=opening_shift,
		company=company,
		pos_profile=pos_profile,
		user=cashier,
	)
	deposits = get_submitted_cash_deposits(
		opening_shift=opening_shift,
		company=company,
		cashier=cashier,
		exclude_payment_entry=exclude_payment_entry,
	)
	deposit_amount = sum(flt(row.get("paid_amount")) for row in deposits)
	available_before_deposits = flt(base.get("available_before"))
	available_cash = available_before_deposits - deposit_amount
	return {
		"opening_cash": flt(base.get("opening_cash")),
		"cash_sales": flt(base.get("cash_sales")),
		"cashier_expenses": flt(base.get("prior_expenses")),
		"submitted_deposits": deposit_amount,
		"submitted_deposit_count": len(deposits),
		"available_before_deposits": available_before_deposits,
		"available_cash": available_cash,
		"source": f"{base.get('source') or 'shift_cash'} + submitted_payment_entry_deposits",
		"message": base.get("message"),
	}


def get_submitted_cash_deposits(
	*,
	opening_shift: str,
	company: str | None = None,
	cashier: str | None = None,
	exclude_payment_entry: str | None = None,
) -> list[dict[str, Any]]:
	if not opening_shift or not has_doctype(PAYMENT_ENTRY_DOCTYPE):
		return []
	for fieldname in CUSTODY_FIELD_DEFS:
		if not has_field(PAYMENT_ENTRY_DOCTYPE, fieldname):
			return []
	filters: dict[str, Any] = {
		"docstatus": 1,
		"payment_type": "Internal Transfer",
		"retailedge_cash_custody_type": CASH_DEPOSIT_TYPE,
		"retailedge_pos_opening_shift": opening_shift,
	}
	if company:
		filters["company"] = company
	if cashier:
		filters["retailedge_cashier"] = cashier
	if exclude_payment_entry:
		filters["name"] = ["!=", exclude_payment_entry]
	rows = frappe.get_all(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		fields=["name", "paid_amount", "paid_from", "paid_to", "posting_date", "retailedge_branch", "retailedge_cashier"],
		order_by="posting_date asc, creation asc",
		limit_page_length=0,
	)
	return [dict(row) for row in rows]


def validate_cash_deposit_before_submit(doc, method=None):
	"""Re-check custody at submit time; drafts intentionally do not reduce custody."""
	if getattr(doc, "doctype", None) != PAYMENT_ENTRY_DOCTYPE:
		return
	if getattr(doc, "retailedge_cash_custody_type", None) != CASH_DEPOSIT_TYPE:
		return
	opening_shift = str(getattr(doc, "retailedge_pos_opening_shift", None) or "").strip()
	cashier = str(getattr(doc, "retailedge_cashier", None) or "").strip()
	company = str(getattr(doc, "company", None) or "").strip()
	if not opening_shift or not cashier or not company:
		frappe.throw(_("RetailEdge cash deposits require cashier, company, and POS opening shift attribution."))
	if not has_doctype("POS Opening Shift") or not frappe.db.exists("POS Opening Shift", opening_shift):
		frappe.throw(_("The linked POS opening shift no longer exists."))

	# Serialize submissions for the same shift. The custody check below therefore
	# sees any earlier deposit committed or still holding this row lock.
	frappe.db.sql("SELECT name FROM `tabPOS Opening Shift` WHERE name = %s FOR UPDATE", (opening_shift,))
	if getattr(doc, "payment_type", None) != "Internal Transfer":
		frappe.throw(_("A RetailEdge cash deposit must remain an Internal Transfer."))
	_get_account(company, getattr(doc, "paid_from", None), expected_type="Cash")
	_get_account(company, getattr(doc, "paid_to", None), expected_type="Bank")
	amount = flt(getattr(doc, "paid_amount", None))
	if amount <= 0 or flt(getattr(doc, "received_amount", None)) != amount:
		frappe.throw(_("Cash deposit paid and received amounts must match and be greater than zero."))

	custody = get_cash_custody_snapshot(
		opening_shift=opening_shift,
		company=company,
		cashier=cashier,
		exclude_payment_entry=getattr(doc, "name", None),
	)
	if amount > flt(custody.get("available_cash")):
		frappe.throw(
			_("This deposit can no longer be submitted because available shift cash is {0}.").format(
				frappe.format_value(custody.get("available_cash"), {"fieldtype": "Currency"})
			)
		)


def _get_account(company: str, account: str | None, *, expected_type: str) -> dict[str, Any]:
	account = str(account or "").strip()
	if not account or not frappe.db.exists("Account", account):
		frappe.throw(_("Account {0} does not exist.").format(account or "(blank)"))
	if not frappe.has_permission("Account", "read", doc=account):
		frappe.throw(_("You do not have permission to use Account {0}.").format(account), frappe.PermissionError)
	fields = ["company", "is_group", "account_type", "account_currency"]
	if has_field("Account", "disabled"):
		fields.append("disabled")
	row = frappe.db.get_value("Account", account, fields, as_dict=True)
	if not row or row.company != company or cint(row.is_group):
		frappe.throw(_("Account {0} is not a posting account for Company {1}.").format(account, company))
	if row.account_type != expected_type:
		frappe.throw(_("Account {0} must be a {1} account.").format(account, expected_type))
	if cint(row.get("disabled")):
		frappe.throw(_("Account {0} is disabled.").format(account))
	return {"account_type": row.account_type, "account_currency": row.account_currency}


def _set_if_field(doc, fieldname: str, value) -> None:
	if has_field(doc.doctype, fieldname):
		setattr(doc, fieldname, value)


def _assert_can_create_payment_entry() -> None:
	if not has_doctype(PAYMENT_ENTRY_DOCTYPE) or not frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Payment Entries."), frappe.PermissionError)


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if not values:
		return {}
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if isinstance(values, frappe._dict):
		return dict(values)
	if isinstance(values, dict):
		return values
	frappe.throw(_("Deposit Cash values must be a mapping."))
	return {}
