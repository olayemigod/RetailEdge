from __future__ import annotations

import frappe
from frappe.utils import cint, cstr

from retailedge.bank_transaction_matching import assert_can_access_bank_transaction_matching
from retailedge.branch_context import has_doctype, has_field

READINESS_READY = "Ready"
READINESS_WARNING = "Warning"
READINESS_BLOCKED = "Blocked"


def _fieldnames(doctype):
	try:
		return {
			field.fieldname
			for field in frappe.get_meta(doctype).fields
			if getattr(field, "fieldname", None)
		}
	except Exception:
		return set()


def _existing_fields(doctype, candidates):
	available = _fieldnames(doctype)
	return [fieldname for fieldname in candidates if fieldname in available]


def _read_row(doctype, name, candidates):
	fields = ["name", *_existing_fields(doctype, candidates)]
	return frappe.db.get_value(doctype, name, fields, as_dict=True) or {}


def _issue(code, message, severity="Blocked", field=None):
	return {
		"code": code,
		"message": message,
		"severity": severity,
		"field": field,
	}


def _bank_account_branch(row):
	return cstr(row.get("retailedge_branch") or row.get("branch")).strip()


def _mode_of_payment_context(company, account):
	if not company or not account or not has_doctype("Mode of Payment Account"):
		return {"configured": False, "modes": [], "conflicts": []}

	fields = _existing_fields(
		"Mode of Payment Account",
		["parent", "company", "default_account"],
	)
	if "parent" not in fields or "default_account" not in fields:
		return {"configured": False, "modes": [], "conflicts": []}

	filters = {}
	if "company" in fields:
		filters["company"] = company
	rows = frappe.get_all(
		"Mode of Payment Account",
		filters=filters,
		fields=fields,
		limit_page_length=500,
	)
	matching = sorted(
		{
			cstr(row.get("parent")).strip()
			for row in rows
			if cstr(row.get("default_account")).strip() == account
			and cstr(row.get("parent")).strip()
		}
	)
	conflicts = [
		{
			"mode_of_payment": cstr(row.get("parent")).strip(),
			"default_account": cstr(row.get("default_account")).strip(),
		}
		for row in rows
		if cstr(row.get("parent")).strip()
		and cstr(row.get("default_account")).strip()
		and cstr(row.get("default_account")).strip() != account
	]
	return {
		"configured": bool(matching),
		"modes": matching,
		"conflicts": conflicts,
	}


def evaluate_bank_account_readiness(bank_account_name, company=None):
	"""Evaluate whether an ERPNext Bank Account is safe for RetailEdge matching/reconciliation.

	Bank Account and Account remain ERPNext accounting truth. Branch and Mode of Payment
	are supporting context; they cannot override a direct company or GL-account problem.
	"""
	name = cstr(bank_account_name).strip()
	requested_company = cstr(company).strip()
	if not name:
		return {
			"bank_account": "",
			"readiness": READINESS_BLOCKED,
			"issues": [_issue("missing_bank_account", "Bank Account is required.")],
			"warnings": [],
		}
	if not has_doctype("Bank Account"):
		return {
			"bank_account": name,
			"readiness": READINESS_BLOCKED,
			"issues": [_issue("missing_bank_account_doctype", "ERPNext Bank Account is unavailable on this site.")],
			"warnings": [],
		}

	bank_row = _read_row(
		"Bank Account",
		name,
		[
			"bank",
			"account",
			"company",
			"disabled",
			"is_company_account",
			"branch",
			"retailedge_branch",
		],
	)
	if not bank_row:
		return {
			"bank_account": name,
			"readiness": READINESS_BLOCKED,
			"issues": [_issue("bank_account_not_found", f"Bank Account {name} was not found.")],
			"warnings": [],
		}

	issues = []
	warnings = []
	bank_company = cstr(bank_row.get("company")).strip()
	ledger_account = cstr(bank_row.get("account")).strip()
	branch = _bank_account_branch(bank_row)

	if has_field("Bank Account", "disabled") and cint(bank_row.get("disabled")):
		issues.append(_issue("bank_account_disabled", "Bank Account is disabled.", field="disabled"))
	if requested_company and bank_company and requested_company != bank_company:
		issues.append(
			_issue(
				"bank_account_company_mismatch",
				f"Bank Account belongs to {bank_company}, not {requested_company}.",
				field="company",
			)
		)
	if not ledger_account:
		issues.append(
			_issue(
				"missing_gl_account",
				"Bank Account is not mapped to an accounting ledger.",
				field="account",
			)
		)

	account_row = {}
	if ledger_account:
		if not has_doctype("Account"):
			issues.append(_issue("missing_account_doctype", "ERPNext Account is unavailable on this site."))
		else:
			account_row = _read_row(
				"Account",
				ledger_account,
				["company", "account_type", "root_type", "is_group", "disabled"],
			)
			if not account_row:
				issues.append(
					_issue(
						"gl_account_not_found",
						f"Mapped accounting ledger {ledger_account} was not found.",
						field="account",
					)
				)
			else:
				account_company = cstr(account_row.get("company")).strip()
				if bank_company and account_company and bank_company != account_company:
					issues.append(
						_issue(
							"gl_company_mismatch",
							f"Mapped ledger belongs to {account_company}, not {bank_company}.",
							field="account",
						)
					)
				if requested_company and account_company and requested_company != account_company:
					issues.append(
						_issue(
							"requested_company_gl_mismatch",
							f"Mapped ledger belongs to {account_company}, not {requested_company}.",
							field="account",
						)
					)
				if has_field("Account", "disabled") and cint(account_row.get("disabled")):
					issues.append(_issue("gl_account_disabled", "Mapped accounting ledger is disabled.", field="account"))
				if cint(account_row.get("is_group")):
					issues.append(_issue("gl_account_is_group", "Mapped accounting ledger is a group account.", field="account"))
				account_type = cstr(account_row.get("account_type")).strip()
				if account_type and account_type != "Bank":
					issues.append(
						_issue(
							"gl_account_not_bank_type",
							f"Mapped ledger is Account Type {account_type}, not Bank.",
							field="account",
						)
					)
				elif not account_type:
					warnings.append(
						_issue(
							"gl_account_type_missing",
							"Mapped ledger has no explicit Bank account type; verify the Chart of Accounts setup.",
							severity="Warning",
							field="account",
						)
					)

	duplicate_count = 0
	if ledger_account and bank_company:
		filters = {"account": ledger_account}
		if has_field("Bank Account", "company"):
			filters["company"] = bank_company
		if has_field("Bank Account", "disabled"):
			filters["disabled"] = 0
		duplicate_count = frappe.db.count("Bank Account", filters=filters)
		if duplicate_count > 1:
			issues.append(
				_issue(
					"ambiguous_bank_account_mapping",
					"Multiple active Bank Accounts map to the same GL account for this company.",
					field="account",
				)
			)

	mop = _mode_of_payment_context(bank_company or requested_company, ledger_account)
	if ledger_account and not mop.get("configured"):
		warnings.append(
			_issue(
				"mode_of_payment_default_missing",
				"No Mode of Payment default currently points to this bank ledger. Direct bank mapping remains usable.",
				severity="Warning",
			)
		)

	if not branch:
		warnings.append(
			_issue(
				"branch_not_restricted",
				"No branch restriction is configured. This is valid for a central/company-wide bank account.",
				severity="Warning",
			)
		)

	readiness = READINESS_BLOCKED if issues else READINESS_WARNING if warnings else READINESS_READY
	return {
		"bank_account": name,
		"bank": bank_row.get("bank"),
		"company": bank_company,
		"resolved_gl_account": ledger_account,
		"branch": branch,
		"branch_scope": "Branch Specific" if branch else "Company Wide / Central",
		"mode_of_payments": mop.get("modes") or [],
		"mode_of_payment_configured": bool(mop.get("configured")),
		"duplicate_mapping_count": duplicate_count,
		"readiness": readiness,
		"issues": issues,
		"warnings": warnings,
		"can_match": readiness != READINESS_BLOCKED,
		"can_reconcile": readiness != READINESS_BLOCKED,
	}


@frappe.whitelist()
def get_bank_account_readiness(bank_account, company=None):
	assert_can_access_bank_transaction_matching()
	return evaluate_bank_account_readiness(bank_account, company=company)


@frappe.whitelist()
def get_banking_readiness(company=None):
	assert_can_access_bank_transaction_matching()
	company = cstr(company).strip()
	if not has_doctype("Bank Account"):
		return {"company": company, "summary": {"ready": 0, "warning": 0, "blocked": 0}, "rows": []}

	filters = {}
	if company and has_field("Bank Account", "company"):
		filters["company"] = company
	if has_field("Bank Account", "disabled"):
		filters["disabled"] = 0
	rows = frappe.get_all(
		"Bank Account",
		filters=filters,
		fields=["name"],
		order_by="name asc",
		limit_page_length=500,
	)
	results = [evaluate_bank_account_readiness(row.get("name"), company=company) for row in rows]
	return {
		"company": company,
		"summary": {
			"ready": sum(1 for row in results if row.get("readiness") == READINESS_READY),
			"warning": sum(1 for row in results if row.get("readiness") == READINESS_WARNING),
			"blocked": sum(1 for row in results if row.get("readiness") == READINESS_BLOCKED),
		},
		"rows": results,
	}
