from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, today

from retailedge.business_expense import (
	BUSINESS_EXPENSE_DOCTYPE,
	_assert_company_access,
	_assert_modified,
	_get_business_expense_for_action,
	get_business_expense,
	resolve_business_expense_branch,
)
from retailedge.business_expense_posting import (
	BUSINESS_EXPENSE_POSTING_ROLES,
	POSTING_DOCUMENT_TYPE,
)
from retailedge.workflow_readiness import _get_active_workflow


@frappe.whitelist()
def get_business_expense_reversal_readiness(name: str) -> dict[str, Any]:
	doc = _get_business_expense_for_action(name)
	return build_business_expense_reversal_readiness(doc)


def build_business_expense_reversal_readiness(doc) -> dict[str, Any]:
	reasons: list[str] = []
	original = _journal_reference_state(
		getattr(doc, "posting_reference_type", None),
		getattr(doc, "posting_reference", None),
	)
	reversal = _journal_reference_state(
		getattr(doc, "reversal_reference_type", None),
		getattr(doc, "reversal_reference", None),
	)

	if cint(getattr(doc, "docstatus", 0)) != 1:
		reasons.append(_("Only submitted Business Expenses can be reversed."))
	if str(getattr(doc, "ledger_status", None) or "") != "Posted":
		if str(getattr(doc, "ledger_status", None) or "") == "Reversed":
			reasons.append(_("This Business Expense has already been reversed."))
		else:
			reasons.append(_("Only posted Business Expenses can be reversed."))
	if not original["submitted"]:
		reasons.append(
			_("The original posting reference must be a submitted Journal Entry.")
		)
	if reversal["exists"]:
		if reversal["submitted"]:
			reasons.append(_("This Business Expense has already been reversed."))
		else:
			reasons.append(
				_(
					"The linked reversal reference is not a submitted Journal Entry. Resolve it through the approved accounting process before retrying."
				)
			)

	try:
		_validate_source_scope(doc)
	except Exception as exc:
		reasons.append(_exception_message(exc))

	permissions = _reversal_permissions(doc)
	if permissions["journal_read_allowed"] and original["submitted"]:
		try:
			original_journal = frappe.get_doc(
				POSTING_DOCUMENT_TYPE,
				original["name"],
			)
			_validate_original_posting_contract(doc, original_journal)
		except Exception as exc:
			reasons.append(_exception_message(exc))

	ready = not reasons
	return {
		"reversal_ready": ready,
		"can_reverse": ready and permissions["can_reverse"],
		"reasons": reasons,
		"reversal_block_reason": "\n".join(reasons) if reasons else "",
		"permissions": permissions,
		"original_reference": original,
		"existing_reversal": reversal,
		"default_posting_date": today(),
	}


@frappe.whitelist(methods=["POST"])
def reverse_business_expense_posting(
	name: str,
	reason: str,
	posting_date: str | None = None,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	_lock_business_expense(name)
	doc = _get_business_expense_for_action(name)

	existing = _journal_reference_state(
		getattr(doc, "reversal_reference_type", None),
		getattr(doc, "reversal_reference", None),
	)
	if existing["submitted"]:
		return _reversal_result(doc, existing["name"], idempotent=True)

	_assert_modified(doc, expected_modified)
	reason = str(reason or "").strip()
	if not reason:
		frappe.throw(_("Reversal reason is required."))
	_assert_reversal_access(doc)

	readiness = build_business_expense_reversal_readiness(doc)
	if not readiness["reversal_ready"]:
		frappe.throw(
			readiness["reversal_block_reason"]
			or _("This Business Expense is not ready for accounting reversal.")
		)
	if not readiness["can_reverse"]:
		frappe.throw(
			_("You do not have permission to reverse this Business Expense posting."),
			frappe.PermissionError,
		)

	original = frappe.get_doc(POSTING_DOCUMENT_TYPE, doc.posting_reference)
	_validate_original_posting_contract(doc, original)
	reversal_date = getdate(posting_date or today())
	if reversal_date < getdate(original.posting_date):
		frappe.throw(
			_(
				"Reversal Posting Date cannot be before the original accounting posting date."
			)
		)

	reversal = _build_reversal_journal_entry(
		doc=doc,
		original=original,
		reason=reason,
		posting_date=reversal_date,
	)
	reversal.insert()
	if not reversal.has_permission("submit"):
		frappe.throw(
			_("You do not have permission to submit the reversal accounting entry."),
			frappe.PermissionError,
		)
	reversal.submit()
	if cint(reversal.docstatus) != 1:
		frappe.throw(_("The reversal accounting entry was not submitted."))

	result_fields = {
		"reversal_reference_type": POSTING_DOCUMENT_TYPE,
		"reversal_reference": reversal.name,
		"reversal_posting_date": reversal_date,
		"reversal_reason": reason,
		"reversed_by": frappe.session.user,
		"reversed_on": now_datetime(),
		"ledger_status": "Reversed",
		"posting_ready": 0,
		"posting_block_reason": None,
	}
	if not _get_active_workflow(BUSINESS_EXPENSE_DOCTYPE):
		result_fields["expense_status"] = "Reversed"
	frappe.db.set_value(
		BUSINESS_EXPENSE_DOCTYPE,
		doc.name,
		result_fields,
		update_modified=True,
	)
	return _reversal_result(
		frappe.get_doc(BUSINESS_EXPENSE_DOCTYPE, doc.name),
		reversal.name,
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


def _validate_source_scope(doc) -> None:
	company = str(getattr(doc, "company", None) or "").strip()
	if not company:
		frappe.throw(_("Company is required before reversal."))
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
				"Business Expense Branch scope changed after posting. Refresh the record before reversing."
			)
		)


def _reversal_permissions(doc) -> dict[str, bool]:
	roles = set(frappe.get_roles(frappe.session.user))
	role_allowed = bool(roles.intersection(BUSINESS_EXPENSE_POSTING_ROLES))
	try:
		write_allowed = bool(doc.has_permission("write"))
		read_allowed = bool(frappe.has_permission(POSTING_DOCUMENT_TYPE, "read"))
		create_allowed = bool(frappe.has_permission(POSTING_DOCUMENT_TYPE, "create"))
		submit_allowed = bool(frappe.has_permission(POSTING_DOCUMENT_TYPE, "submit"))
	except Exception:
		write_allowed = False
		read_allowed = False
		create_allowed = False
		submit_allowed = False
	return {
		"role_allowed": role_allowed,
		"write_allowed": write_allowed,
		"journal_read_allowed": read_allowed,
		"journal_create_allowed": create_allowed,
		"journal_submit_allowed": submit_allowed,
		"can_reverse": role_allowed
		and write_allowed
		and read_allowed
		and create_allowed
		and submit_allowed,
	}


def _assert_reversal_access(doc) -> None:
	permissions = _reversal_permissions(doc)
	if not permissions["role_allowed"]:
		frappe.throw(
			_("You do not have Business Expense accounting-reversal access."),
			frappe.PermissionError,
		)
	if not permissions["write_allowed"]:
		frappe.throw(
			_("You do not have permission to update this Business Expense."),
			frappe.PermissionError,
		)
	if not permissions["journal_read_allowed"]:
		frappe.throw(
			_("You do not have permission to read the original accounting entry."),
			frappe.PermissionError,
		)
	if not permissions["journal_create_allowed"]:
		frappe.throw(
			_("You do not have permission to create the reversal accounting entry."),
			frappe.PermissionError,
		)
	if not permissions["journal_submit_allowed"]:
		frappe.throw(
			_("You do not have permission to submit the reversal accounting entry."),
			frappe.PermissionError,
		)


def _journal_reference_state(reference_type, reference) -> dict[str, Any]:
	reference_type = str(reference_type or "").strip()
	reference = str(reference or "").strip()
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


def _validate_original_posting_contract(doc, journal) -> None:
	if not journal.has_permission("read"):
		frappe.throw(
			_("You do not have permission to read the original accounting entry."),
			frappe.PermissionError,
		)
	if cint(journal.docstatus) != 1:
		frappe.throw(_("Original accounting entry is not submitted."))
	if str(journal.company or "") != str(doc.company or ""):
		frappe.throw(_("Original accounting entry belongs to another Company."))

	amount = flt(doc.amount)
	rows = list(journal.accounts or [])
	if len(rows) != 2:
		frappe.throw(
			_(
				"Original accounting entry no longer matches the two-line RetailEdge Business Expense posting contract."
			)
		)

	expense_rows = [
		row
		for row in rows
		if row.account == doc.expense_account
		and _same_amount(row.debit_in_account_currency, amount)
		and _same_amount(row.credit_in_account_currency, 0)
	]
	payment_rows = [
		row
		for row in rows
		if row.account == doc.payment_account
		and _same_amount(row.credit_in_account_currency, amount)
		and _same_amount(row.debit_in_account_currency, 0)
	]
	if len(expense_rows) != 1 or len(payment_rows) != 1:
		frappe.throw(
			_(
				"Original accounting entry does not match the Business Expense accounts and amount. Reverse it through accountant review instead."
			)
		)

	expense_row = expense_rows[0]
	if getattr(doc, "cost_center", None) and expense_row.cost_center != doc.cost_center:
		frappe.throw(
			_("Original accounting entry Cost Center no longer matches this Business Expense.")
		)
	if getattr(doc, "project", None) and expense_row.project != doc.project:
		frappe.throw(
			_("Original accounting entry Project no longer matches this Business Expense.")
		)

	meta = frappe.get_meta(POSTING_DOCUMENT_TYPE)
	if getattr(doc, "branch", None) and meta.has_field("retailedge_branch"):
		if str(getattr(journal, "retailedge_branch", None) or "") != str(doc.branch):
			frappe.throw(
				_("Original accounting entry Branch no longer matches this Business Expense.")
			)


def _build_reversal_journal_entry(*, doc, original, reason: str, posting_date):
	amount = flt(doc.amount)
	journal = frappe.new_doc(POSTING_DOCUMENT_TYPE)
	journal.voucher_type = "Journal Entry"
	journal.company = doc.company
	journal.posting_date = posting_date
	journal.user_remark = _(
		"Reversal of Business Expense {0}; original {1}. Reason: {2}"
	).format(doc.name, original.name, reason)

	meta = frappe.get_meta(POSTING_DOCUMENT_TYPE)
	if getattr(doc, "branch", None) and meta.has_field("retailedge_branch"):
		journal.retailedge_branch = doc.branch

	journal.append(
		"accounts",
		{
			"account": doc.payment_account,
			"debit_in_account_currency": amount,
			"credit_in_account_currency": 0,
		},
	)
	expense_row = {
		"account": doc.expense_account,
		"debit_in_account_currency": 0,
		"credit_in_account_currency": amount,
	}
	if getattr(doc, "cost_center", None):
		expense_row["cost_center"] = doc.cost_center
	if getattr(doc, "project", None):
		expense_row["project"] = doc.project
	journal.append("accounts", expense_row)
	return journal


def _same_amount(value, expected) -> bool:
	return abs(flt(value) - flt(expected)) < 0.000001


def _reversal_result(doc, journal_name: str, *, idempotent: bool) -> dict[str, Any]:
	return {
		"reversed": True,
		"idempotent": idempotent,
		"reversal_document_type": POSTING_DOCUMENT_TYPE,
		"reversal_reference": journal_name,
		"expense": get_business_expense(doc.name),
	}


def _exception_message(exc: Exception) -> str:
	message = getattr(exc, "message", None) or str(exc)
	return str(message or _("Business Expense reversal validation failed.")).strip()
