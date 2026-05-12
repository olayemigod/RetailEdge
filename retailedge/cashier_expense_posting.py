from __future__ import annotations

from types import SimpleNamespace

import frappe
from frappe.utils import flt, now_datetime

from retailedge.cashier_expense import append_cashier_expense_action_log, user_has_any_role
from retailedge.utils.settings import get_retailedge_settings


POSTING_REFRESH_ROLES = {
	"System Manager",
	"Accounts Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}


def get_cashier_expense_posting_settings():
	try:
		settings = get_retailedge_settings()
	except Exception:
		settings = SimpleNamespace()

	return {
		"enabled": bool(getattr(settings, "enable_cashier_expense_accounting_posting", 0)),
		"posting_document_type": getattr(settings, "cashier_expense_posting_document_type", None) or "Journal Entry",
		"require_approval_before_posting": bool(getattr(settings, "require_cashier_expense_approval_before_posting", 1)),
		"allow_rejected_posting": bool(getattr(settings, "allow_rejected_cashier_expense_posting", 0)),
		"remark_template": getattr(settings, "cashier_expense_posting_remark_template", None)
		or "RetailEdge Cashier Expense {expense_name} - {expense_category}",
		"default_payable_account": getattr(settings, "default_cashier_expense_payable_account", None) or None,
	}


def build_cashier_expense_posting_preview(expense_doc_or_name):
	doc = _coerce_expense_doc(expense_doc_or_name)
	settings = get_cashier_expense_posting_settings()
	reasons = []
	posting_reference = getattr(doc, "posting_reference", None)
	expense_status = getattr(doc, "expense_status", None)
	ledger_status = getattr(doc, "ledger_status", None)
	company = getattr(doc, "company", None)
	amount = flt(getattr(doc, "amount", 0))
	posting_date = getattr(doc, "expense_date", None)
	debit_account = getattr(doc, "expense_account", None)
	credit_account = getattr(doc, "payment_account", None) or settings.get("default_payable_account")
	cost_center = getattr(doc, "cost_center", None)

	if doc.docstatus == 2 or expense_status == "Cancelled":
		reasons.append("Cancelled expenses are not eligible for future ledger posting.")
	if ledger_status == "Posted":
		reasons.append("This cashier expense is already marked as Posted.")
	if amount <= 0:
		reasons.append("Amount must be greater than zero before posting can be prepared.")
	if not company:
		reasons.append("Company is required for posting readiness.")
	if not posting_date:
		reasons.append("Expense Date is required for posting readiness.")
	if not debit_account:
		reasons.append("Expense Account is required for posting readiness.")
	if not credit_account:
		reasons.append("Payment Account is required for posting readiness.")

	if debit_account:
		reasons.extend(_validate_debit_account(debit_account, company))
	if credit_account:
		reasons.extend(_validate_credit_account(credit_account, company))

	if settings["require_approval_before_posting"] and expense_status != "Pending Ledger":
		reasons.append("Expense must be in Pending Ledger status before posting is allowed.")
	if expense_status == "Rejected" and not settings["allow_rejected_posting"]:
		reasons.append("Rejected cashier expenses are blocked from posting by RetailEdge Settings.")
	if posting_reference:
		reasons.append("This cashier expense already has a posting reference linked.")

	remarks = _render_remarks(
		settings["remark_template"],
		{
			"expense_name": doc.name,
			"expense_category": getattr(doc, "expense_category", None) or "",
		},
	)
	preview_lines = []
	if debit_account and amount > 0:
		preview_lines.append(
			{
				"account": debit_account,
				"debit": amount,
				"credit": 0.0,
				"cost_center": cost_center,
			}
		)
	if credit_account and amount > 0:
		preview_lines.append(
			{
				"account": credit_account,
				"debit": 0.0,
				"credit": amount,
				"cost_center": cost_center,
			}
		)

	posting_ready = not reasons
	preview = {
		"expense_name": doc.name,
		"posting_ready": posting_ready,
		"posting_block_reason": "\n".join(reasons) if reasons else None,
		"posting_document_type": settings["posting_document_type"],
		"company": company,
		"posting_date": posting_date,
		"amount": amount,
		"debit_account": debit_account,
		"credit_account": credit_account,
		"cost_center": cost_center,
		"remarks": remarks,
		"preview_lines": preview_lines,
	}
	preview["posting_preview"] = _build_preview_text(preview)
	return preview


def get_cashier_expense_posting_preview(expense_name):
	return build_cashier_expense_posting_preview(expense_name)


def refresh_cashier_expense_posting_readiness(expense_name):
	preview = get_cashier_expense_posting_preview(expense_name)
	frappe.db.set_value(
		"RetailEdge Cashier Expense",
		expense_name,
		{
			"posting_ready": 1 if preview["posting_ready"] else 0,
			"posting_block_reason": preview.get("posting_block_reason"),
			"resolved_debit_account": preview.get("debit_account"),
			"resolved_credit_account": preview.get("credit_account"),
			"resolved_posting_cost_center": preview.get("cost_center"),
			"posting_preview": preview.get("posting_preview"),
			"last_readiness_refresh_on": now_datetime(),
			"last_readiness_refresh_by": frappe.session.user,
		},
		update_modified=False,
	)
	append_cashier_expense_action_log(
		expense_name,
		action="Posting Readiness Refreshed",
		previous_status=None,
		new_status=None,
		remarks=preview.get("posting_block_reason"),
		context={
			"posting_ready": preview.get("posting_ready"),
			"posting_document_type": preview.get("posting_document_type"),
		},
	)
	return preview


def refresh_pending_cashier_expense_posting_readiness(filters=None):
	_assert_refresh_access()
	filters = frappe.parse_json(filters) if filters else {}
	query_filters = {"docstatus": ["!=", 2], "expense_status": ["!=", "Cancelled"]}
	for fieldname in ("company", "branch", "pos_profile", "linked_pos_opening_shift", "expense_status"):
		if filters.get(fieldname):
			query_filters[fieldname] = filters[fieldname]

	rows = frappe.get_all("RetailEdge Cashier Expense", filters=query_filters, fields=["name"], limit_page_length=0)
	updated = 0
	blocked = 0
	for row in rows:
		preview = refresh_cashier_expense_posting_readiness(row.name)
		if preview.get("posting_ready"):
			updated += 1
		else:
			blocked += 1
	return {"updated_count": updated, "blocked_count": blocked}


def assert_can_refresh_posting_readiness(user=None):
	_assert_refresh_access(user=user)


def _assert_refresh_access(user=None):
	if not user_has_any_role(user=user, roles=POSTING_REFRESH_ROLES):
		frappe.throw("You do not have permission to refresh cashier expense posting readiness.", frappe.PermissionError)


def _coerce_expense_doc(expense_doc_or_name):
	if getattr(expense_doc_or_name, "doctype", None) == "RetailEdge Cashier Expense":
		return expense_doc_or_name
	return frappe.get_doc("RetailEdge Cashier Expense", expense_doc_or_name)


def _validate_debit_account(account, company):
	return _validate_account(account, company, require_expense_root=True)


def _validate_credit_account(account, company):
	return _validate_account(account, company, require_expense_root=False)


def _validate_account(account, company, require_expense_root=False):
	if not account:
		return []
	reasons = []
	if not frappe.db.exists("Account", account):
		return [f"Account {account} does not exist."]
	account_doc = frappe.get_cached_doc("Account", account)
	account_company = getattr(account_doc, "company", None)
	if company and account_company and account_company != company:
		reasons.append(f"Account {account} does not belong to company {company}.")
	if require_expense_root and getattr(account_doc, "root_type", None) != "Expense":
		reasons.append(f"Debit account {account} must have root type Expense.")
	if getattr(account_doc, "is_group", 0):
		reasons.append(f"Account {account} must not be a group account.")
	return reasons


def _render_remarks(template, values):
	try:
		return template.format(**values)
	except Exception:
		return f"RetailEdge Cashier Expense {values.get('expense_name')} - {values.get('expense_category')}"


def _build_preview_text(preview):
	lines = [
		f"Posting Ready: {'Yes' if preview.get('posting_ready') else 'No'}",
		f"Document Type: {preview.get('posting_document_type')}",
		f"Company: {preview.get('company') or ''}",
		f"Posting Date: {preview.get('posting_date') or ''}",
		f"Amount: {preview.get('amount') or 0}",
		f"Debit Account: {preview.get('debit_account') or ''}",
		f"Credit Account: {preview.get('credit_account') or ''}",
		f"Cost Center: {preview.get('cost_center') or ''}",
		f"Remarks: {preview.get('remarks') or ''}",
	]
	if preview.get("posting_block_reason"):
		lines.append(f"Block Reason: {preview['posting_block_reason']}")
	if preview.get("preview_lines"):
		lines.append("Preview Lines:")
		for line in preview["preview_lines"]:
			lines.append(
				f"- {line.get('account')}: debit {flt(line.get('debit'))}, credit {flt(line.get('credit'))}, cost center {line.get('cost_center') or ''}"
			)
	return "\n".join(lines)
