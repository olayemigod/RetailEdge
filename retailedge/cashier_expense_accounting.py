from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.cashier_expense import append_cashier_expense_action_log, user_has_any_role
from retailedge.cashier_expense_posting import (
	build_cashier_expense_posting_preview,
	get_cashier_expense_posting_settings,
)
from retailedge.operating_context import get_operational_branch_scope

POSTING_DOCUMENT_TYPE = "Journal Entry"
CONTROLLED_POSTING_ROLES = {
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
}
DIRECT_CAPTURE_ROLES = CONTROLLED_POSTING_ROLES | {
	"RetailEdge Cashier",
	"RetailEdgeCashier",
}


@frappe.whitelist(methods=["POST"])
def post_cashier_expense_to_accounts(
	expense_name: str,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	return _post_cashier_expense_to_accounts(
		expense_name,
		expected_modified=expected_modified,
		automatic=False,
	)


def attempt_direct_cashier_expense_posting(expense_doc_or_name) -> dict[str, Any]:
	"""Best-effort direct posting without losing an already-recorded till expense.

	Direct Posting is an explicit merchant policy, but it does not bypass ERPNext
	Journal Entry permissions. If accounting permission/readiness fails, the
	physical Cashier Expense remains submitted and is marked Failed for follow-up.
	"""
	settings = get_cashier_expense_posting_settings()
	if not settings["enabled"] or settings["posting_mode"] != "Direct Posting":
		return {"attempted": False, "posted": False}

	doc = _coerce_expense_doc(expense_doc_or_name)
	if cint(getattr(doc, "docstatus", 0)) != 1:
		return {"attempted": False, "posted": False}

	try:
		result = _post_cashier_expense_to_accounts(doc.name, automatic=True)
		result["attempted"] = True
		return result
	except Exception as exc:
		message = _exception_message(exc)
		frappe.db.set_value(
			"RetailEdge Cashier Expense",
			doc.name,
			{
				"ledger_status": "Failed",
				"posting_ready": 0,
				"posting_block_reason": message,
				"user_message": _(
					"Expense recorded against the till, but accounting posting needs attention: {0}"
				).format(message),
			},
			update_modified=False,
		)
		append_cashier_expense_action_log(
			doc.name,
			action="Direct Posting Failed",
			previous_status=getattr(doc, "expense_status", None),
			new_status=getattr(doc, "expense_status", None),
			remarks=message,
			context={"posting_mode": "Direct Posting"},
		)
		return {
			"attempted": True,
			"posted": False,
			"ledger_status": "Failed",
			"message": message,
		}


def _post_cashier_expense_to_accounts(
	expense_name: str,
	*,
	expected_modified: str | None = None,
	automatic: bool,
) -> dict[str, Any]:
	_lock_cashier_expense(expense_name)
	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)

	existing = _posting_reference_state(doc)
	if existing["submitted"]:
		return _posting_result(doc, existing["name"], idempotent=True)

	if expected_modified and str(getattr(doc, "modified", "") or "") != str(expected_modified):
		frappe.throw(_("This Cashier Expense changed after you opened it. Refresh before posting."))

	settings = get_cashier_expense_posting_settings()
	if not settings["enabled"]:
		frappe.throw(_("Cashier Expense accounting posting is disabled in RetailEdge Settings."))
	if settings["posting_document_type"] != POSTING_DOCUMENT_TYPE:
		frappe.throw(_("Cashier Expenses can currently post only through Journal Entry."))
	_assert_posting_access(doc, settings=settings, automatic=automatic)

	preview = build_cashier_expense_posting_preview(doc)
	if not preview["posting_ready"]:
		frappe.throw(
			preview.get("posting_block_reason")
			or _("This Cashier Expense is not ready for accounting posting.")
		)

	savepoint = None
	if automatic:
		savepoint = f"retailedge_cashier_direct_{frappe.generate_hash(length=8)}"
		frappe.db.savepoint(savepoint)

	try:
		journal = _build_journal_entry(doc, preview)
		journal.insert()
		if not journal.has_permission("submit"):
			frappe.throw(
				_("You do not have permission to submit the Journal Entry."),
				frappe.PermissionError,
			)
		journal.submit()
		if cint(journal.docstatus) != 1:
			frappe.throw(_("The Journal Entry was not submitted."))

		previous_status = str(getattr(doc, "expense_status", None) or "Submitted")
		frappe.db.set_value(
			"RetailEdge Cashier Expense",
			doc.name,
			{
				"posting_reference_type": POSTING_DOCUMENT_TYPE,
				"posting_reference": journal.name,
				"ledger_status": "Posted",
				"expense_status": "Posted",
				"posting_ready": 0,
				"posting_block_reason": None,
				"user_message": None,
			},
			update_modified=True,
		)
		append_cashier_expense_action_log(
			doc.name,
			action="Posted to Accounts",
			previous_status=previous_status,
			new_status="Posted",
			context={
				"posting_mode": settings["posting_mode"],
				"journal_entry": journal.name,
			},
		)
		result = _posting_result(
			frappe.get_doc("RetailEdge Cashier Expense", doc.name),
			journal.name,
			idempotent=False,
		)
	except Exception:
		if savepoint:
			frappe.db.rollback(save_point=savepoint)
		raise
	else:
		if savepoint:
			frappe.db.release_savepoint(savepoint)
		return result


def _assert_posting_access(doc, *, settings: dict[str, Any], automatic: bool) -> None:
	roles = DIRECT_CAPTURE_ROLES if automatic and settings["posting_mode"] == "Direct Posting" else CONTROLLED_POSTING_ROLES
	if not user_has_any_role(roles=roles):
		frappe.throw(
			_("You do not have Cashier Expense accounting-posting access."),
			frappe.PermissionError,
		)
	if not doc.has_permission("write"):
		frappe.throw(
			_("You do not have permission to update this Cashier Expense."),
			frappe.PermissionError,
		)
	company = str(getattr(doc, "company", None) or "").strip()
	branch = str(getattr(doc, "branch", None) or "").strip()
	if company:
		scope = get_operational_branch_scope(company, user=frappe.session.user)
		if scope.get("restricted") and branch not in set(scope.get("allowed_branches") or []):
			frappe.throw(
				_("You do not have active Branch access to post this Cashier Expense."),
				frappe.PermissionError,
			)
	for ptype, label in (("read", "read"), ("create", "create"), ("submit", "submit")):
		if not frappe.has_permission(POSTING_DOCUMENT_TYPE, ptype):
			frappe.throw(
				_("You do not have permission to {0} Journal Entries.").format(label),
				frappe.PermissionError,
			)


def _build_journal_entry(doc, preview: dict[str, Any]):
	amount = flt(doc.amount)
	journal = frappe.new_doc(POSTING_DOCUMENT_TYPE)
	journal.voucher_type = "Journal Entry"
	journal.company = doc.company
	journal.posting_date = doc.expense_date
	journal.user_remark = preview.get("remarks") or _(
		"Cashier Expense {0} - {1}"
	).format(doc.name, doc.expense_category)

	if getattr(doc, "branch", None) and frappe.get_meta(POSTING_DOCUMENT_TYPE).has_field("retailedge_branch"):
		journal.retailedge_branch = doc.branch

	debit_row = {
		"account": preview["debit_account"],
		"debit_in_account_currency": amount,
		"credit_in_account_currency": 0,
	}
	if preview.get("cost_center"):
		debit_row["cost_center"] = preview["cost_center"]
	journal.append("accounts", debit_row)
	journal.append(
		"accounts",
		{
			"account": preview["credit_account"],
			"debit_in_account_currency": 0,
			"credit_in_account_currency": amount,
		},
	)
	return journal


def _posting_reference_state(doc) -> dict[str, Any]:
	reference_type = str(getattr(doc, "posting_reference_type", None) or "").strip()
	reference = str(getattr(doc, "posting_reference", None) or "").strip()
	if not reference:
		return {"exists": False, "submitted": False, "name": "", "type": reference_type}
	if reference_type != POSTING_DOCUMENT_TYPE:
		return {"exists": True, "submitted": False, "name": reference, "type": reference_type}
	docstatus = frappe.db.get_value(POSTING_DOCUMENT_TYPE, reference, "docstatus")
	return {
		"exists": True,
		"submitted": cint(docstatus) == 1,
		"name": reference,
		"type": reference_type,
	}


def _lock_cashier_expense(expense_name: str) -> None:
	expense_name = str(expense_name or "").strip()
	if not expense_name:
		frappe.throw(_("Cashier Expense name is required."))
	rows = frappe.db.sql(
		"SELECT name FROM `tabRetailEdge Cashier Expense` WHERE name = %s FOR UPDATE",
		values=(expense_name,),
	)
	if not rows:
		frappe.throw(_("Cashier Expense {0} does not exist.").format(expense_name))


def _coerce_expense_doc(expense_doc_or_name):
	if getattr(expense_doc_or_name, "doctype", None) == "RetailEdge Cashier Expense":
		return expense_doc_or_name
	return frappe.get_doc("RetailEdge Cashier Expense", expense_doc_or_name)


def _posting_result(doc, journal_name: str, *, idempotent: bool) -> dict[str, Any]:
	return {
		"posted": True,
		"idempotent": idempotent,
		"posting_document_type": POSTING_DOCUMENT_TYPE,
		"posting_reference": journal_name,
		"expense_name": doc.name,
		"expense_status": getattr(doc, "expense_status", None),
		"ledger_status": getattr(doc, "ledger_status", None),
	}


def _exception_message(exc: Exception) -> str:
	message = getattr(exc, "message", None) or str(exc)
	return str(message or _("Cashier Expense accounting posting failed.")).strip()
