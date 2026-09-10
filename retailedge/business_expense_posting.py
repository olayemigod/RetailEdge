from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.business_expense import (
	BUSINESS_EXPENSE_DOCTYPE,
	_assert_company_access,
	_assert_modified,
	_get_business_expense_for_action,
	_validate_cost_center,
	_validate_expense_account,
	_validate_payment_account,
	_validate_project,
	get_business_expense,
	get_business_expense_settings,
	resolve_business_expense_branch,
)

POSTING_DOCUMENT_TYPE = "Journal Entry"
BUSINESS_EXPENSE_POSTING_ROLES = {
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
}


@frappe.whitelist()
def get_business_expense_posting_readiness(name: str) -> dict[str, Any]:
	doc = _get_business_expense_for_action(name)
	return build_business_expense_posting_readiness(doc)


def build_business_expense_posting_readiness(doc) -> dict[str, Any]:
	settings = get_business_expense_settings()
	reasons: list[str] = []
	reference = _posting_reference_state(doc)

	if not settings["enabled"]:
		reasons.append(_("Business Expenses are disabled in RetailEdge Settings."))
	if not settings["accounting_posting_enabled"]:
		reasons.append(_("Business Expense accounting posting is disabled in RetailEdge Settings."))
	if settings["posting_document_type"] != POSTING_DOCUMENT_TYPE:
		reasons.append(_("Business Expenses can currently post only through ERPNext Journal Entry."))

	if cint(getattr(doc, "docstatus", 0)) != 1:
		reasons.append(_("Only submitted Business Expenses can be posted to accounts."))
	if str(getattr(doc, "expense_status", None) or "") not in {"Approved", "Pending Ledger"}:
		reasons.append(_("Business Expense must be approved before posting to accounts."))
	if str(getattr(doc, "ledger_status", None) or "") != "Pending Ledger":
		reasons.append(_("Business Expense must be in Pending Ledger status before posting."))
	if flt(getattr(doc, "amount", 0)) <= 0:
		reasons.append(_("Amount must be greater than zero before posting."))

	if reference["exists"]:
		if reference["submitted"]:
			reasons.append(_("This Business Expense is already posted to accounts."))
		else:
			reasons.append(
				_(
					"The linked accounting reference is not a submitted Journal Entry. Resolve it through the approved accounting process before retrying."
				)
			)

	for validator in (
		_validate_source_scope,
		_validate_source_accounts,
		_validate_company_currency_accounts,
	):
		try:
			validator(doc)
		except Exception as exc:
			reasons.append(_exception_message(exc))

	permissions = _posting_permissions(doc)
	ready = not reasons
	return {
		"posting_ready": ready,
		"can_post": ready and permissions["can_post"],
		"posting_document_type": POSTING_DOCUMENT_TYPE,
		"reasons": reasons,
		"posting_block_reason": "\n".join(reasons) if reasons else "",
		"permissions": permissions,
		"existing_reference": reference,
		"amount": flt(getattr(doc, "amount", 0)),
		"company": getattr(doc, "company", None) or "",
		"expense_account": getattr(doc, "expense_account", None) or "",
		"payment_account": getattr(doc, "payment_account", None) or "",
		"cost_center": getattr(doc, "cost_center", None) or "",
		"project": getattr(doc, "project", None) or "",
	}


@frappe.whitelist(methods=["POST"])
def post_business_expense_to_accounts(
	name: str,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	_lock_business_expense(name)
	doc = _get_business_expense_for_action(name)

	existing = _posting_reference_state(doc)
	if existing["submitted"]:
		return _posting_result(doc, existing["name"], idempotent=True)

	_assert_modified(doc, expected_modified)
	_assert_posting_access(doc)
	readiness = build_business_expense_posting_readiness(doc)
	if not readiness["posting_ready"]:
		frappe.throw(
			readiness["posting_block_reason"]
			or _("This Business Expense is not ready for accounting posting.")
		)
	if not readiness["can_post"]:
		frappe.throw(
			_("You do not have permission to post this Business Expense to accounts."),
			frappe.PermissionError,
		)

	journal = _build_journal_entry(doc)
	journal.insert()
	if not journal.has_permission("submit"):
		frappe.throw(
			_("You do not have permission to submit the Journal Entry."),
			frappe.PermissionError,
		)
	journal.submit()
	if cint(journal.docstatus) != 1:
		frappe.throw(_("ERPNext did not submit the Journal Entry."))

	frappe.db.set_value(
		BUSINESS_EXPENSE_DOCTYPE,
		doc.name,
		{
			"posting_reference_type": POSTING_DOCUMENT_TYPE,
			"posting_reference": journal.name,
			"posting_ready": 1,
			"posting_block_reason": None,
			"ledger_status": "Posted",
			"expense_status": "Posted",
		},
		update_modified=True,
	)
	return _posting_result(
		frappe.get_doc(BUSINESS_EXPENSE_DOCTYPE, doc.name),
		journal.name,
		idempotent=False,
	)


def _lock_business_expense(name: str) -> None:
	name = str(name or "").strip()
	if not name:
		frappe.throw(_("Business Expense name is required."))
	rows = frappe.db.sql(
		f"SELECT name FROM `tab{BUSINESS_EXPENSE_DOCTYPE}` WHERE name = %s FOR UPDATE",
		values=(name,),
	)
	if not rows:
		frappe.throw(_("Business Expense {0} does not exist.").format(name))


def _assert_posting_access(doc) -> None:
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles.intersection(BUSINESS_EXPENSE_POSTING_ROLES):
		frappe.throw(
			_("You do not have Business Expense accounting-posting access."),
			frappe.PermissionError,
		)
	if not doc.has_permission("write"):
		frappe.throw(
			_("You do not have permission to update this Business Expense."),
			frappe.PermissionError,
		)
	if not frappe.has_permission(POSTING_DOCUMENT_TYPE, "create"):
		frappe.throw(
			_("You do not have permission to create Journal Entries."),
			frappe.PermissionError,
		)
	if not frappe.has_permission(POSTING_DOCUMENT_TYPE, "submit"):
		frappe.throw(
			_("You do not have permission to submit Journal Entries."),
			frappe.PermissionError,
		)


def _posting_permissions(doc) -> dict[str, bool]:
	roles = set(frappe.get_roles(frappe.session.user))
	role_allowed = bool(roles.intersection(BUSINESS_EXPENSE_POSTING_ROLES))
	try:
		write_allowed = bool(doc.has_permission("write"))
		create_allowed = bool(frappe.has_permission(POSTING_DOCUMENT_TYPE, "create"))
		submit_allowed = bool(frappe.has_permission(POSTING_DOCUMENT_TYPE, "submit"))
	except Exception:
		write_allowed = False
		create_allowed = False
		submit_allowed = False
	return {
		"role_allowed": role_allowed,
		"write_allowed": write_allowed,
		"journal_create_allowed": create_allowed,
		"journal_submit_allowed": submit_allowed,
		"can_post": role_allowed and write_allowed and create_allowed and submit_allowed,
	}


def _validate_source_scope(doc) -> None:
	company = str(getattr(doc, "company", None) or "").strip()
	if not company:
		frappe.throw(_("Company is required before posting."))
	_assert_company_access(company)
	branch = str(getattr(doc, "branch", None) or "").strip()
	resolved = resolve_business_expense_branch(
		company=company,
		branch=branch,
		require_when_restricted=True,
	)
	if resolved != branch:
		frappe.throw(
			_(
				"Business Expense Branch scope changed after submission. Refresh or correct the operational record before posting."
			)
		)


def _validate_source_accounts(doc) -> None:
	company = str(getattr(doc, "company", None) or "").strip()
	expense_account = str(getattr(doc, "expense_account", None) or "").strip()
	payment_account = str(getattr(doc, "payment_account", None) or "").strip()
	if not expense_account:
		frappe.throw(_("Expense Account is required before posting."))
	if not payment_account:
		frappe.throw(_("Paid From account is required before posting."))
	_validate_expense_account(expense_account, company)
	_validate_payment_account(payment_account, company)
	if getattr(doc, "cost_center", None):
		_validate_cost_center(doc.cost_center, company)
	if getattr(doc, "project", None):
		_validate_project(doc.project, company)


def _validate_company_currency_accounts(doc) -> None:
	company = str(getattr(doc, "company", None) or "").strip()
	company_currency = str(
		frappe.db.get_value("Company", company, "default_currency") or ""
	).strip()
	if not company_currency:
		frappe.throw(_("Company default currency is required before posting."))
	for fieldname, label in (
		("expense_account", _("Expense Account")),
		("payment_account", _("Paid From account")),
	):
		account = str(getattr(doc, fieldname, None) or "").strip()
		account_currency = str(
			frappe.db.get_value("Account", account, "account_currency")
			or company_currency
		).strip()
		if account_currency != company_currency:
			frappe.throw(
				_(
					"{0} must use the Company default currency for this simplified Business Expense posting flow."
				).format(label)
			)


def _posting_reference_state(doc) -> dict[str, Any]:
	reference_type = str(
		getattr(doc, "posting_reference_type", None) or ""
	).strip()
	reference = str(getattr(doc, "posting_reference", None) or "").strip()
	if not reference:
		return {
			"exists": False,
			"submitted": False,
			"type": reference_type,
			"name": "",
			"docstatus": None,
		}
	if reference_type != POSTING_DOCUMENT_TYPE:
		return {
			"exists": True,
			"submitted": False,
			"type": reference_type,
			"name": reference,
			"docstatus": None,
		}
	docstatus = frappe.db.get_value(POSTING_DOCUMENT_TYPE, reference, "docstatus")
	return {
		"exists": True,
		"submitted": cint(docstatus) == 1,
		"type": reference_type,
		"name": reference,
		"docstatus": cint(docstatus) if docstatus is not None else None,
	}


def _build_journal_entry(doc):
	amount = flt(doc.amount)
	journal = frappe.new_doc(POSTING_DOCUMENT_TYPE)
	journal.voucher_type = "Journal Entry"
	journal.company = doc.company
	journal.posting_date = doc.expense_date
	journal.user_remark = _("Business Expense {0} - {1}").format(
		doc.name,
		doc.expense_category,
	)

	meta = frappe.get_meta(POSTING_DOCUMENT_TYPE)
	if getattr(doc, "branch", None) and meta.has_field("retailedge_branch"):
		journal.retailedge_branch = doc.branch

	debit_row = {
		"account": doc.expense_account,
		"debit_in_account_currency": amount,
		"credit_in_account_currency": 0,
	}
	if getattr(doc, "cost_center", None):
		debit_row["cost_center"] = doc.cost_center
	if getattr(doc, "project", None):
		debit_row["project"] = doc.project
	journal.append("accounts", debit_row)
	journal.append(
		"accounts",
		{
			"account": doc.payment_account,
			"debit_in_account_currency": 0,
			"credit_in_account_currency": amount,
		},
	)
	return journal


def _posting_result(doc, journal_name: str, *, idempotent: bool) -> dict[str, Any]:
	return {
		"posted": True,
		"idempotent": idempotent,
		"posting_document_type": POSTING_DOCUMENT_TYPE,
		"posting_reference": journal_name,
		"expense": get_business_expense(doc.name),
	}


def _exception_message(exc: Exception) -> str:
	message = getattr(exc, "message", None) or str(exc)
	return str(message or _("Business Expense posting validation failed.")).strip()
