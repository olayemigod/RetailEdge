from __future__ import annotations

import frappe
from frappe.utils import cint, cstr, flt, getdate

from retailedge.bank_transaction_matching import (
	assert_can_access_bank_transaction_matching,
	normalize_bank_transaction,
)
from retailedge.branch_context import has_doctype, has_field
from retailedge.reconciliation_handoff import (
	get_bank_transaction_reconciliation_context,
	get_payment_event_reconciliation_context,
)
from retailedge.reporting_scope import validate_report_scope

READINESS_READY = "Ready"
READINESS_WARNING = "Warning"
READINESS_BLOCKED = "Blocked"

EVIDENCE_MATCH = "Match"
EVIDENCE_MISMATCH = "Mismatch"
EVIDENCE_SUPPORTING = "Supporting"
EVIDENCE_NOT_AVAILABLE = "Not Available"
EVIDENCE_NOT_APPLICABLE = "Not Applicable"


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


def _bank_accounts_for_ledger(account, company=None):
	account = cstr(account).strip()
	company = cstr(company).strip()
	if not account or not has_doctype("Bank Account"):
		return []
	filters = {"account": account}
	if company and has_field("Bank Account", "company"):
		filters["company"] = company
	if has_field("Bank Account", "disabled"):
		filters["disabled"] = 0
	fields = ["name"]
	for fieldname in ("bank", "account", "company", "branch", "retailedge_branch"):
		if has_field("Bank Account", fieldname):
			fields.append(fieldname)
	return frappe.get_all(
		"Bank Account",
		filters=filters,
		fields=fields,
		order_by="name asc",
		limit_page_length=20,
	)


def _status_for_pair(left, right, *, supporting=False, not_applicable=False):
	left = cstr(left).strip()
	right = cstr(right).strip()
	if not_applicable:
		return EVIDENCE_NOT_APPLICABLE
	if left and right:
		return EVIDENCE_SUPPORTING if supporting and left == right else EVIDENCE_MATCH if left == right else EVIDENCE_MISMATCH
	return EVIDENCE_NOT_AVAILABLE


def _date_status(bank_date, candidate_date):
	if not bank_date or not candidate_date:
		return EVIDENCE_NOT_AVAILABLE, None
	try:
		days = abs((getdate(bank_date) - getdate(candidate_date)).days)
	except Exception:
		return EVIDENCE_NOT_AVAILABLE, None
	return (EVIDENCE_MATCH if days == 0 else EVIDENCE_SUPPORTING), days


def _journal_entry_business_context(name, bank_ledger, direction):
	"""Classify a reviewed Journal Entry from its non-bank ledger structure."""
	if not name or not bank_ledger or not has_doctype("Account"):
		return {"candidate_category": "Journal Entry Match", "transaction_category": "Other Outflow" if direction == "Outflow" else "Other Income"}
	rows = frappe.get_all(
		"Journal Entry Account",
		filters={"parent": name, "docstatus": 1},
		fields=["account"],
		limit_page_length=50,
	)
	counterpart_accounts = list(
		dict.fromkeys(
			cstr(row.get("account")).strip()
			for row in rows
			if cstr(row.get("account")).strip()
			and cstr(row.get("account")).strip() != bank_ledger
		)
	)
	if not counterpart_accounts:
		return {"candidate_category": "Journal Entry Match", "transaction_category": "Other Outflow" if direction == "Outflow" else "Other Income"}
	account_fields = ["name"]
	for fieldname in ("root_type", "account_type"):
		if has_field("Account", fieldname):
			account_fields.append(fieldname)
	account_rows = frappe.get_all(
		"Account",
		filters={"name": ["in", counterpart_accounts]},
		fields=account_fields,
		limit_page_length=len(counterpart_accounts),
	)
	has_expense = any(cstr(row.get("root_type")).strip() == "Expense" for row in account_rows)
	has_bank = any(cstr(row.get("account_type")).strip() == "Bank" for row in account_rows)
	if direction == "Outflow" and has_expense:
		return {"candidate_category": "Expense Payment", "transaction_category": "Expense"}
	if has_bank:
		return {
			"candidate_category": "Deposit to Bank" if direction == "Inflow" else "Bank Transfer",
			"transaction_category": "Deposit to Bank" if direction == "Inflow" else "Bank Transfer",
		}
	return {
		"candidate_category": "Journal Entry Match",
		"transaction_category": "Other Income" if direction == "Inflow" else "Other Outflow",
	}


def _journal_entry_reconciliation_context(name, match_doc):
	"""Resolve the exact Journal Entry bank-side row for Review Match evidence.

	Journal Entries do not have paid_from/paid_to fields, so evidence must be resolved
	from the reviewed bank ledger and the canonical Bank Transaction direction. Fail
	closed when the reviewed ledger is missing or is not represented exactly once.
	"""
	name = cstr(name).strip()
	match_doc = frappe._dict(match_doc or {})
	if not name or not has_doctype("Journal Entry") or not has_doctype("Journal Entry Account"):
		return {}
	# docstatus is a standard Frappe column, not a normal DocField in meta.fields.
	# Read the submitted voucher directly so the live evidence path cannot silently
	# drop docstatus and reject an otherwise valid Journal Entry as a draft.
	row = frappe.db.get_value(
		"Journal Entry",
		name,
		["name", "posting_date", "company", "voucher_type", "cheque_no", "docstatus"],
		as_dict=True,
	) or {}
	if not row or cint(row.get("docstatus")) != 1:
		return {}

	direction = cstr(match_doc.get("direction") or match_doc.get("bank_direction")).strip()
	bank_ledger = cstr(
		match_doc.get("resolved_payment_account") or match_doc.get("payment_account")
	).strip()
	if direction not in {"Inflow", "Outflow"} or not bank_ledger:
		return {}

	account_rows = frappe.get_all(
		"Journal Entry Account",
		filters={"parent": name, "account": bank_ledger, "docstatus": 1},
		fields=[
			"account",
			"debit_in_account_currency",
			"credit_in_account_currency",
			"party_type",
			"party",
		],
		limit_page_length=5,
	)
	if len(account_rows) != 1:
		return {}
	bank_row = frappe._dict(account_rows[0])
	candidate_amount = flt(
		bank_row.get("debit_in_account_currency")
		if direction == "Inflow"
		else bank_row.get("credit_in_account_currency")
	)
	if candidate_amount <= 0:
		return {}
	business_context = _journal_entry_business_context(name, bank_ledger, direction)

	return {
		"candidate_doctype": "Journal Entry",
		"candidate_name": name,
		"candidate_date": row.get("posting_date"),
		"candidate_account": bank_ledger,
		"candidate_amount": candidate_amount,
		"candidate_mode_of_payment": "",
		"candidate_reference": row.get("cheque_no"),
		"candidate_party": bank_row.get("party"),
		"candidate_party_type": bank_row.get("party_type"),
		"candidate_branch": "",
		"candidate_company": row.get("company"),
		"candidate_docstatus": row.get("docstatus"),
		"payment_event_source": "Journal Entry",
		"candidate_category": business_context.get("candidate_category"),
		"transaction_category": business_context.get("transaction_category"),
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


def build_match_account_evidence(match_name):
	"""Return human-readable, server-authoritative bank identity evidence for Review Match."""
	name = cstr(match_name).strip()
	fields = [
		"name", "bank_transaction", "suggested_document_type", "suggested_document",
		"company", "branch", "bank_account", "bank_amount", "candidate_amount",
		"transaction_date", "bank_reference", "payment_mode", "bank_direction",
		"payment_account", "resolved_payment_account",
	]
	fields = [field for field in fields if field == "name" or has_field("RetailEdge Bank Transaction Match", field)]
	match = frappe.db.get_value("RetailEdge Bank Transaction Match", name, fields, as_dict=True) or {}
	if not match:
		frappe.throw(f"Bank match review {name} was not found.")

	bank_transaction_name = cstr(match.get("bank_transaction")).strip()
	bank_context = frappe._dict(get_bank_transaction_reconciliation_context(bank_transaction_name))
	normalized = frappe._dict(normalize_bank_transaction(bank_transaction_name))
	direction = cstr(normalized.get("direction") or match.get("bank_direction")).strip()
	bank_account = cstr(bank_context.get("bank_account") or match.get("bank_account")).strip()
	company = cstr(bank_context.get("company") or match.get("company")).strip()
	bank_readiness = evaluate_bank_account_readiness(bank_account, company=company) if bank_account else {}
	bank_gl = cstr(bank_readiness.get("resolved_gl_account")).strip()

	match_for_candidate = frappe._dict(dict(match))
	match_for_candidate["direction"] = direction
	match_for_candidate["bank_direction"] = direction
	if cstr(match.get("suggested_document_type")).strip() == "Journal Entry" and bank_gl:
		# Review evidence must be hydrated from the live, validated statement bank ledger.
		# Older review rows may predate Journal Entry payment_account persistence, so do not
		# let blank/stale match metadata hide otherwise deterministic ERPNext accounting evidence.
		match_for_candidate["resolved_payment_account"] = bank_gl
		match_for_candidate["payment_account"] = bank_gl
	candidate_context = frappe._dict(
		get_payment_event_reconciliation_context(
			match.get("suggested_document_type"),
			match.get("suggested_document"),
			match_doc=match_for_candidate,
		)
	)
	if (
		cstr(match.get("suggested_document_type")).strip() == "Journal Entry"
		and not cstr(candidate_context.get("candidate_account")).strip()
	):
		candidate_context = frappe._dict(
			_journal_entry_reconciliation_context(
				match.get("suggested_document"),
				match_for_candidate,
			)
		)
	candidate_gl = cstr(candidate_context.get("candidate_account")).strip()
	candidate_company = cstr(candidate_context.get("candidate_company")).strip()
	if not candidate_company and match.get("suggested_document_type") and match.get("suggested_document"):
		if has_field(match.get("suggested_document_type"), "company"):
			candidate_company = cstr(
				frappe.db.get_value(match.get("suggested_document_type"), match.get("suggested_document"), "company") or ""
			).strip()
	candidate_bank_accounts = _bank_accounts_for_ledger(candidate_gl, company=candidate_company or company)
	candidate_bank = candidate_bank_accounts[0] if len(candidate_bank_accounts) == 1 else {}
	candidate_bank_account = cstr(candidate_bank.get("name")).strip()
	candidate_bank_name = cstr(candidate_bank.get("bank")).strip()

	bank_reference = cstr(bank_context.get("reference") or match.get("bank_reference")).strip()
	candidate_reference = cstr(candidate_context.get("candidate_reference")).strip()
	bank_branch = cstr(bank_context.get("branch") or match.get("branch")).strip()
	candidate_branch = cstr(candidate_context.get("candidate_branch")).strip()
	mode_of_payment = cstr(candidate_context.get("candidate_mode_of_payment") or match.get("payment_mode")).strip()
	bank_amount = flt(bank_context.get("bank_transaction_amount") or match.get("bank_amount"))
	candidate_amount = flt(candidate_context.get("candidate_amount") or match.get("candidate_amount"))
	amount_status = EVIDENCE_MATCH if abs(bank_amount - candidate_amount) <= 0.01 else EVIDENCE_MISMATCH
	date_status, date_distance_days = _date_status(
		bank_context.get("bank_transaction_date") or match.get("transaction_date"),
		candidate_context.get("candidate_date"),
	)
	bank_account_status = EVIDENCE_NOT_AVAILABLE
	if bank_gl and candidate_gl:
		bank_account_status = EVIDENCE_MATCH if bank_gl == candidate_gl else EVIDENCE_MISMATCH
	company_status = _status_for_pair(company, candidate_company)
	branch_status = _status_for_pair(bank_branch, candidate_branch, supporting=True)
	if not bank_branch and not candidate_branch:
		branch_status = EVIDENCE_NOT_APPLICABLE
	reference_status = EVIDENCE_NOT_AVAILABLE
	if bank_reference and candidate_reference:
		reference_status = EVIDENCE_MATCH if bank_reference.lower() == candidate_reference.lower() else EVIDENCE_SUPPORTING

	payment_side_label = "Bank-side Account"
	if cstr(match.get("suggested_document_type")).strip() == "Payment Entry":
		payment_side_label = "Paid From" if direction == "Outflow" else "Paid To" if direction == "Inflow" else payment_side_label

	return {
		"match_name": name,
		"direction": direction,
		"candidate_category": candidate_context.get("candidate_category"),
		"transaction_category": candidate_context.get("transaction_category"),
		"statement": {
			"bank_transaction": bank_transaction_name,
			"bank_account": bank_account,
			"bank": bank_readiness.get("bank"),
			"gl_account": bank_gl,
			"company": company,
			"branch": bank_branch,
			"amount": bank_amount,
			"date": bank_context.get("bank_transaction_date") or match.get("transaction_date"),
			"reference": bank_reference,
		},
		"accounting": {
			"doctype": match.get("suggested_document_type"),
			"name": match.get("suggested_document"),
			"bank_account": candidate_bank_account,
			"bank": candidate_bank_name,
			"bank_account_candidates": [row.get("name") for row in candidate_bank_accounts],
			"gl_account": candidate_gl,
			"gl_account_label": payment_side_label,
			"company": candidate_company,
			"branch": candidate_branch,
			"mode_of_payment": mode_of_payment,
			"amount": candidate_amount,
			"date": candidate_context.get("candidate_date"),
			"reference": candidate_reference,
		},
		"evidence": [
			{"key": "bank_account", "label": "Bank Account", "status": bank_account_status, "statement": bank_account, "accounting": candidate_bank_account or candidate_gl},
			{"key": "gl_account", "label": "GL Account", "status": bank_account_status, "statement": bank_gl, "accounting": candidate_gl},
			{"key": "company", "label": "Company", "status": company_status, "statement": company, "accounting": candidate_company},
			{"key": "direction", "label": "Direction", "status": EVIDENCE_MATCH if direction else EVIDENCE_NOT_AVAILABLE, "statement": direction, "accounting": payment_side_label},
			{"key": "amount", "label": "Amount", "status": amount_status, "statement": bank_amount, "accounting": candidate_amount},
			{"key": "date", "label": "Date", "status": date_status, "statement": bank_context.get("bank_transaction_date") or match.get("transaction_date"), "accounting": candidate_context.get("candidate_date"), "distance_days": date_distance_days},
			{"key": "reference", "label": "Reference", "status": reference_status, "statement": bank_reference, "accounting": candidate_reference},
			{"key": "branch", "label": "Branch", "status": branch_status, "statement": bank_branch, "accounting": candidate_branch},
			{"key": "mode_of_payment", "label": "Mode of Payment", "status": EVIDENCE_SUPPORTING if mode_of_payment else EVIDENCE_NOT_AVAILABLE, "statement": "", "accounting": mode_of_payment},
		],
		"banking_readiness": bank_readiness,
	}


@frappe.whitelist()
def get_match_account_evidence(match_name):
	assert_can_access_bank_transaction_matching()
	return build_match_account_evidence(match_name)


def _assert_bank_account_readiness_scope(bank_account, company=None):
	"""Resolve one Bank Account through permission-aware Company/Branch read scope."""
	user = frappe.session.user
	name = cstr(bank_account).strip()
	requested_company = cstr(company).strip()
	if not name:
		frappe.throw("Bank Account is required.", frappe.ValidationError)
	if not frappe.has_permission("Bank Account", "read", user=user):
		frappe.throw("You do not have permission to view Bank Accounts.", frappe.PermissionError)
	if not has_field("Bank Account", "company"):
		frappe.throw(
			"Bank Account Company attribution is required for Banking Readiness.",
			frappe.ValidationError,
		)

	branch_field = "retailedge_branch" if has_field("Bank Account", "retailedge_branch") else ""
	fields = ["name", "company"]
	if branch_field:
		fields.append(branch_field)
	filters = {"name": name}
	if requested_company:
		filters["company"] = requested_company
	rows = frappe.get_list(
		"Bank Account",
		filters=filters,
		fields=fields,
		limit_page_length=1,
	)
	if not rows:
		frappe.throw("You do not have permission to view this Bank Account.", frappe.PermissionError)

	row = frappe._dict(rows[0])
	bank_company = cstr(row.get("company")).strip()
	if not bank_company:
		frappe.throw(
			"Bank Account Company attribution is required for Banking Readiness.",
			frappe.ValidationError,
		)
	scope = validate_report_scope(
		company=bank_company,
		branch="",
		user=user,
		require_branch_when_restricted=False,
	)
	if scope.get("restricted"):
		allowed_branches = list(
			dict.fromkeys(
				cstr(branch).strip()
				for branch in scope.get("allowed_branches") or []
				if cstr(branch).strip()
			)
		)
		if not allowed_branches:
			frappe.throw(
				f"Your Branch banking access is not active for Company {bank_company}.",
				frappe.PermissionError,
			)
		if not branch_field:
			frappe.throw(
				"Bank Account Branch attribution is required for restricted Banking Readiness.",
				frappe.ValidationError,
			)
		bank_branch = cstr(row.get(branch_field)).strip()
		if not bank_branch or bank_branch not in allowed_branches:
			frappe.throw(
				"You do not have permission to view this Bank Account in Banking Readiness.",
				frappe.PermissionError,
			)
	return row


@frappe.whitelist()
def get_bank_account_readiness(bank_account, company=None):
	assert_can_access_bank_transaction_matching()
	_assert_bank_account_readiness_scope(bank_account, company=company)
	return evaluate_bank_account_readiness(bank_account, company=company)


MAX_BANKING_READINESS_ROWS = 500


def _bank_account_rows_for_readiness(company=None):
	"""Return Bank Accounts within the current reader's Company and Branch scope."""
	user = frappe.session.user
	company = cstr(company).strip()
	if not frappe.has_permission("Bank Account", "read", user=user):
		frappe.throw("You do not have permission to view Bank Accounts.", frappe.PermissionError)

	if company:
		companies = [company]
	else:
		if not frappe.has_permission("Company", "read", user=user):
			frappe.throw("You do not have permission to view Companies.", frappe.PermissionError)
		companies = frappe.get_list(
			"Company",
			pluck="name",
			order_by="name asc",
			limit_page_length=MAX_BANKING_READINESS_ROWS,
		)

	if companies and not has_field("Bank Account", "company"):
		frappe.throw(
			"Bank Account Company attribution is required for Banking Readiness.",
			frappe.ValidationError,
		)

	branch_field = (
		"retailedge_branch" if has_field("Bank Account", "retailedge_branch") else ""
	)
	rows_by_name = {}
	for allowed_company in companies:
		allowed_company = cstr(allowed_company).strip()
		if not allowed_company:
			continue
		scope = validate_report_scope(
			company=allowed_company,
			branch="",
			user=user,
			require_branch_when_restricted=False,
		)
		filters = {"company": allowed_company}
		if has_field("Bank Account", "disabled"):
			filters["disabled"] = 0
		if scope.get("restricted"):
			allowed_branches = list(
				dict.fromkeys(
					cstr(branch).strip()
					for branch in scope.get("allowed_branches") or []
					if cstr(branch).strip()
				)
			)
			if not allowed_branches:
				frappe.throw(
					f"Your Branch banking access is not active for Company {allowed_company}.",
					frappe.PermissionError,
				)
			if not branch_field:
				frappe.throw(
					"Bank Account Branch attribution is required for restricted Banking Readiness.",
					frappe.ValidationError,
				)
			# Deliberately excludes blank/company-wide accounts for restricted readers.
			filters[branch_field] = ["in", allowed_branches]

		for row in frappe.get_list(
			"Bank Account",
			filters=filters,
			fields=["name"],
			order_by="name asc",
			limit_page_length=MAX_BANKING_READINESS_ROWS,
		):
			name = cstr(row.get("name")).strip()
			if name:
				rows_by_name[name] = row

	return [
		rows_by_name[name]
		for name in sorted(rows_by_name)[:MAX_BANKING_READINESS_ROWS]
	]


@frappe.whitelist()
def get_banking_readiness(company=None):
	assert_can_access_bank_transaction_matching()
	company = cstr(company).strip()
	if not has_doctype("Bank Account"):
		return {"company": company, "summary": {"ready": 0, "warning": 0, "blocked": 0}, "rows": []}

	rows = _bank_account_rows_for_readiness(company)
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
