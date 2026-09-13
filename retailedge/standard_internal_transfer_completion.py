from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime

from retailedge.bank_account_policy import validate_cash_deposit_bank_destination
from retailedge.branch_context import has_field
from retailedge.cash_custody import CASH_DEPOSIT_TYPE, get_cash_custody_snapshot
from retailedge.operating_context import (
	get_operating_context,
	get_operational_branch_scope,
	resolve_operational_branch,
)
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_workflow_readiness


PAYMENT_ENTRY_DOCTYPE = "Payment Entry"
INTERNAL_TRANSFER = "Internal Transfer"
_LOCK_TABLE = "tabPayment Entry"


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _assert_read(doctype: str, name: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name or "(blank)"))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(
			_("You do not have permission to read {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)


def _get_payment_entry(name: str):
	name = _clean(name)
	if not name or not frappe.db.exists(PAYMENT_ENTRY_DOCTYPE, name):
		frappe.throw(_("Payment Entry {0} does not exist.").format(name or "(blank)"))
	doc = frappe.get_doc(PAYMENT_ENTRY_DOCTYPE, name)
	if not frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "read", doc=doc):
		frappe.throw(
			_("You do not have permission to read Payment Entry {0}.").format(name),
			frappe.PermissionError,
		)
	return doc


def _lock_payment_entry(name: str) -> None:
	rows = frappe.db.sql(
		f"SELECT name FROM `{_LOCK_TABLE}` WHERE name = %s FOR UPDATE",
		(_clean(name),),
	)
	if not rows:
		frappe.throw(_("Payment Entry {0} no longer exists.").format(name))


def _branch_field() -> str:
	if has_field(PAYMENT_ENTRY_DOCTYPE, "retailedge_branch"):
		return "retailedge_branch"
	if has_field(PAYMENT_ENTRY_DOCTYPE, "branch"):
		return "branch"
	return ""


def _payment_branch(doc) -> str:
	fieldname = _branch_field()
	return _clean(doc.get(fieldname)) if fieldname else ""


def _validate_transfer_context(doc) -> tuple[str, str]:
	company = _clean(doc.get("company"))
	if not company:
		frappe.throw(_("Payment Entry {0} has no Company.").format(doc.name))
	_assert_read("Company", company)

	branch = _payment_branch(doc)
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	if branch:
		branch = _clean(
			resolve_operational_branch(
				company,
				branch,
				user=frappe.session.user,
			).get("branch")
		)
	elif scope["restricted"]:
		frappe.throw(
			_("Payment Entry {0} has no Branch attribution for your restricted access.").format(
				doc.name
			),
			frappe.PermissionError,
		)

	operating = get_operating_context() or {}
	operating_company = _clean(operating.get("company"))
	operating_branch = _clean(operating.get("branch"))
	if operating_company and operating_company != company:
		frappe.throw(
			_("Payment Entry {0} belongs to another Company. Change Operating Context before completing it.").format(
				doc.name
			),
			frappe.PermissionError,
		)
	if operating_branch and branch and operating_branch != branch:
		frappe.throw(
			_("Payment Entry {0} does not belong to the current Operating Branch.").format(doc.name),
			frappe.PermissionError,
		)
	return company, branch


def _standard_transfer_blockers(doc) -> list[str]:
	blockers: list[str] = []
	if cint(doc.docstatus) != 0:
		blockers.append(_("Only draft Payment Entries can use standard Internal Transfer completion."))
	if doc.get("payment_type") != INTERNAL_TRANSFER:
		blockers.append(_("Only Internal Transfer Payment Entries are supported by this standard path."))

	if _clean(doc.get("party_type")) or _clean(doc.get("party")):
		blockers.append(_("Party-based Payment Entries require Advanced ERPNext review."))
	if list(doc.get("references") or []):
		blockers.append(_("Allocated Payment Entries require Advanced ERPNext review."))
	if list(doc.get("deductions") or []):
		blockers.append(_("Payment Entries with deductions require Advanced ERPNext review."))
	if abs(flt(doc.get("difference_amount"))) > 0.005:
		blockers.append(_("Payment Entries with exchange differences require Advanced ERPNext review."))
	if cint(doc.get("book_advance_payments_in_separate_party_account")):
		blockers.append(_("Separate party-account advances require Advanced ERPNext review."))

	custody_type = _clean(doc.get("retailedge_cash_custody_type"))
	if custody_type and custody_type != CASH_DEPOSIT_TYPE:
		blockers.append(_("Unsupported RetailEdge cash-custody Payment Entry requires Advanced ERPNext review."))

	return list(dict.fromkeys(blockers))


def _account_details(*, company: str, account: str) -> dict[str, Any]:
	account = _clean(account)
	_assert_read("Account", account)
	fields = ["company", "is_group", "account_type", "account_currency"]
	if has_field("Account", "disabled"):
		fields.append("disabled")
	row = frappe.db.get_value("Account", account, fields, as_dict=True)
	if not row or _clean(row.company) != company or cint(row.is_group):
		frappe.throw(
			_("Account {0} is not a posting account for Company {1}.").format(account, company)
		)
	if cint(row.get("disabled")):
		frappe.throw(_("Account {0} is disabled.").format(account))
	return {
		"name": account,
		"account_type": _clean(row.account_type),
		"account_currency": _clean(row.account_currency),
	}


def _validate_accounts(doc, *, company: str) -> dict[str, Any]:
	blockers: list[str] = []
	from_account = _clean(doc.get("paid_from"))
	to_account = _clean(doc.get("paid_to"))
	if not from_account or not to_account:
		blockers.append(_("From Account and To Account are required."))
		return {"from": None, "to": None, "company_currency": "", "blockers": blockers}
	if from_account == to_account:
		blockers.append(_("From Account and To Account must be different."))

	from_details = _account_details(company=company, account=from_account)
	to_details = _account_details(company=company, account=to_account)
	for details in (from_details, to_details):
		if details["account_type"] not in {"Bank", "Cash"}:
			blockers.append(
				_("Standard internal transfers support Bank or Cash posting accounts only.")
			)

	company_currency = _clean(
		frappe.db.get_value("Company", company, "default_currency")
	)
	if not company_currency:
		blockers.append(_("Company {0} has no default currency.").format(company))
	elif (
		from_details["account_currency"] != company_currency
		or to_details["account_currency"] != company_currency
	):
		blockers.append(_("Multi-currency internal transfers require Advanced ERPNext review."))

	paid_amount = flt(doc.get("paid_amount"))
	received_amount = flt(doc.get("received_amount"))
	if paid_amount <= 0 or received_amount <= 0 or abs(paid_amount - received_amount) > 0.005:
		blockers.append(_("Internal Transfer paid and received amounts must match and be greater than zero."))

	if (
		(from_details["account_type"] == "Bank" or to_details["account_type"] == "Bank")
		and not _clean(doc.get("reference_no"))
	):
		blockers.append(_("Reference No is required when a Bank account is involved."))

	return {
		"from": from_details,
		"to": to_details,
		"company_currency": company_currency,
		"blockers": list(dict.fromkeys(blockers)),
	}


def _validate_cash_deposit_context(
	doc,
	*,
	company: str,
	branch: str,
	account_context: dict[str, Any],
) -> dict[str, Any]:
	if _clean(doc.get("retailedge_cash_custody_type")) != CASH_DEPOSIT_TYPE:
		return {"is_cash_deposit": False, "custody": None, "blockers": []}

	blockers: list[str] = []
	cashier = _clean(doc.get("retailedge_cashier"))
	opening_shift = _clean(doc.get("retailedge_pos_opening_shift"))
	if not cashier:
		blockers.append(_("Cash Deposit has no cashier attribution."))
	if not opening_shift:
		blockers.append(_("Cash Deposit has no POS opening-shift attribution."))

	from_details = account_context.get("from") or {}
	to_details = account_context.get("to") or {}
	if from_details.get("account_type") != "Cash":
		blockers.append(_("A standard Cash Deposit must move funds from a Cash account."))
	if to_details.get("account_type") != "Bank":
		blockers.append(_("A standard Cash Deposit must move funds to a Bank account."))

	# Reuse the existing Bank Account policy. Final serialized custody enforcement
	# remains in cash_custody.validate_cash_deposit_before_submit via doc_events.
	validate_cash_deposit_bank_destination(doc)

	custody = None
	if opening_shift and cashier:
		if not frappe.db.exists("POS Opening Shift", opening_shift):
			blockers.append(_("The linked POS opening shift no longer exists."))
		else:
			custody = get_cash_custody_snapshot(
				opening_shift=opening_shift,
				company=company,
				cashier=cashier,
				exclude_payment_entry=doc.name,
			)
			available_cash = flt(custody.get("available_cash"))
			if flt(doc.get("paid_amount")) > available_cash + 0.005:
				blockers.append(
					_("Cash Deposit amount now exceeds the current available shift cash.")
				)

	return {
		"is_cash_deposit": True,
		"cashier": cashier,
		"opening_shift": opening_shift,
		"branch": branch,
		"custody": custody,
		"blockers": list(dict.fromkeys(blockers)),
	}


def _build_preview(doc) -> dict[str, Any]:
	company, branch = _validate_transfer_context(doc)
	blockers = _standard_transfer_blockers(doc)
	account_context = _validate_accounts(doc, company=company)
	blockers.extend(account_context["blockers"])
	deposit_context = _validate_cash_deposit_context(
		doc,
		company=company,
		branch=branch,
		account_context=account_context,
	)
	blockers.extend(deposit_context["blockers"])
	blockers = list(dict.fromkeys(blockers))

	workflow_readiness = get_workflow_readiness(
		doctype=PAYMENT_ENTRY_DOCTYPE,
		doc=doc,
	)
	workflow_controlled = _clean(workflow_readiness.get("source")) == "frappe"
	if (
		not workflow_controlled
		and not blockers
		and not frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "submit", doc=doc)
	):
		blockers.append(_("You do not have permission to submit this Payment Entry."))

	return {
		"doctype": PAYMENT_ENTRY_DOCTYPE,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"status": _clean(doc.get("status")) or ("Draft" if cint(doc.docstatus) == 0 else ""),
		"transfer_kind": "Cash Deposit" if deposit_context["is_cash_deposit"] else "Cash / Bank Transfer",
		"company": company,
		"branch": branch,
		"from_account": _clean(doc.get("paid_from")),
		"from_account_type": (account_context.get("from") or {}).get("account_type", ""),
		"to_account": _clean(doc.get("paid_to")),
		"to_account_type": (account_context.get("to") or {}).get("account_type", ""),
		"amount": flt(doc.get("paid_amount")),
		"currency": account_context.get("company_currency") or "",
		"reference_no": _clean(doc.get("reference_no")),
		"cashier": deposit_context.get("cashier") or "",
		"pos_opening_shift": deposit_context.get("opening_shift") or "",
		"custody": deposit_context.get("custody"),
		"blockers": blockers,
		"can_submit": bool(
			not blockers
			and not workflow_controlled
			and cint(doc.docstatus) == 0
		),
		"workflow_readiness": workflow_readiness,
		"workflow_eligible": bool(
			workflow_controlled
			and not blockers
			and cint(doc.docstatus) == 0
		),
		"persistence": "none",
		"source_of_truth": "ERPNext Payment Entry",
		"route": f"/app/payment-entry/{doc.name}",
	}


def _assert_expected_modified(doc, expected_modified: str | None) -> str:
	expected_modified = _clean(expected_modified)
	if not expected_modified:
		frappe.throw(
			_("The reviewed Payment Entry version is required. Refresh completion review."),
			frappe.TimestampMismatchError,
		)
	try:
		expected = get_datetime(expected_modified)
		current = get_datetime(doc.modified)
	except Exception:
		frappe.throw(_("Invalid reviewed Payment Entry version."), frappe.ValidationError)
	if expected != current:
		frappe.throw(
			_("Payment Entry {0} changed after completion review. Refresh before continuing.").format(
				doc.name
			),
			frappe.TimestampMismatchError,
		)
	return expected_modified


@frappe.whitelist()
def get_standard_internal_transfer_completion_preview(name: str) -> dict[str, Any]:
	"""Return a persistence-free completion review for one standard Internal Transfer."""
	doc = _get_payment_entry(name)
	return _build_preview(doc)


@frappe.whitelist(methods=["POST"])
def submit_standard_internal_transfer(
	name: str,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	"""Submit one reviewed standard Internal Transfer through native ERPNext."""
	name = _clean(name)
	_lock_payment_entry(name)
	doc = _get_payment_entry(name)
	_assert_expected_modified(doc, expected_modified)
	company, branch = _validate_transfer_context(doc)

	blockers = _standard_transfer_blockers(doc)
	account_context = _validate_accounts(doc, company=company)
	blockers.extend(account_context["blockers"])
	deposit_context = _validate_cash_deposit_context(
		doc,
		company=company,
		branch=branch,
		account_context=account_context,
	)
	blockers.extend(deposit_context["blockers"])
	if blockers:
		frappe.throw("<br>".join(list(dict.fromkeys(blockers))))

	workflow_readiness = get_workflow_readiness(
		doctype=PAYMENT_ENTRY_DOCTYPE,
		doc=doc,
	)
	if _clean(workflow_readiness.get("source")) == "frappe":
		frappe.throw(
			_(
				"Payment Entry is controlled by active Workflow {0}. Use the available workflow action in EdgeSuite."
			).format(workflow_readiness.get("workflow") or _("Payment Entry Workflow")),
			frappe.ValidationError,
		)

	if not frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "submit", doc=doc):
		frappe.throw(
			_("You do not have permission to submit this Payment Entry."),
			frappe.PermissionError,
		)

	# Native ERPNext submit remains the only GL/Payment Ledger authority.
	# Marked Cash Deposits also execute the existing before_submit custody hook.
	doc.submit()
	if cint(doc.docstatus) != 1:
		frappe.throw(_("ERPNext did not submit Payment Entry {0}.").format(name))
	doc.reload()
	return {
		"doctype": PAYMENT_ENTRY_DOCTYPE,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"status": _clean(doc.get("status")) or "Submitted",
		"transfer_kind": "Cash Deposit" if deposit_context["is_cash_deposit"] else "Cash / Bank Transfer",
		"company": company,
		"branch": branch,
		"from_account": _clean(doc.get("paid_from")),
		"to_account": _clean(doc.get("paid_to")),
		"amount": flt(doc.get("paid_amount")),
		"source_of_truth": "ERPNext Payment Entry submit",
		"route": f"/app/payment-entry/{doc.name}",
	}


@frappe.whitelist(methods=["POST"])
def apply_standard_internal_transfer_workflow_action(
	name: str,
	action: str,
	expected_modified: str | None = None,
	expected_workflow_state: str | None = None,
) -> dict[str, Any]:
	"""Apply one Frappe Workflow action to a reviewed standard Internal Transfer."""
	name = _clean(name)
	action = _clean(action)
	if not action:
		frappe.throw(_("Workflow action is required."))

	_lock_payment_entry(name)
	doc = _get_payment_entry(name)
	expected_modified = _assert_expected_modified(doc, expected_modified)
	company, branch = _validate_transfer_context(doc)

	blockers = _standard_transfer_blockers(doc)
	account_context = _validate_accounts(doc, company=company)
	blockers.extend(account_context["blockers"])
	deposit_context = _validate_cash_deposit_context(
		doc,
		company=company,
		branch=branch,
		account_context=account_context,
	)
	blockers.extend(deposit_context["blockers"])
	if blockers:
		frappe.throw("<br>".join(list(dict.fromkeys(blockers))))

	workflow_readiness = get_workflow_readiness(
		doctype=PAYMENT_ENTRY_DOCTYPE,
		doc=doc,
	)
	if _clean(workflow_readiness.get("source")) != "frappe":
		frappe.throw(
			_("No active Frappe Workflow owns this Payment Entry."),
			frappe.ValidationError,
		)

	return apply_document_workflow_action(
		doctype=PAYMENT_ENTRY_DOCTYPE,
		name=name,
		action=action,
		expected_modified=expected_modified,
		expected_state=str(expected_workflow_state or ""),
	)
