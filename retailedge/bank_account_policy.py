from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint

from retailedge.branch_context import has_doctype, has_field, validate_user_branch_access

BANK_ACCOUNT_DOCTYPE = "Bank Account"
BRANCH_FIELD = "retailedge_branch"
MAX_LINK_RESULTS = 20
MAX_SEARCH_SCAN = 100


def ensure_bank_account_branch_custom_field():
	"""Idempotently add optional RetailEdge Branch scoping to ERPNext Bank Account."""
	if not has_doctype(BANK_ACCOUNT_DOCTYPE) or not has_doctype("Branch"):
		return {}
	insert_after = "company" if has_field(BANK_ACCOUNT_DOCTYPE, "company") else "account"
	custom_fields = {
		BANK_ACCOUNT_DOCTYPE: [
			{
				"fieldname": BRANCH_FIELD,
				"label": "RetailEdge Branch",
				"fieldtype": "Link",
				"options": "Branch",
				"insert_after": insert_after,
				"in_standard_filter": 1,
				"description": (
					"Optional. Leave blank to make this company bank account available to all permitted branches; "
					"set a branch to restrict RetailEdge selection to that branch."
				),
			}
		]
	}
	create_custom_fields(custom_fields, ignore_validate=True, update=True)
	return custom_fields


def validate_bank_account_branch(doc, method=None):
	"""Keep optional Bank Account branch scope consistent with its company and user permissions."""
	if getattr(doc, "doctype", None) != BANK_ACCOUNT_DOCTYPE or not has_field(BANK_ACCOUNT_DOCTYPE, BRANCH_FIELD):
		return
	branch = str(getattr(doc, BRANCH_FIELD, None) or "").strip()
	if not branch:
		return
	company = str(getattr(doc, "company", None) or "").strip()
	if not company:
		frappe.throw(_("Company is required when a RetailEdge Branch is set on a Bank Account."))
	_assert_branch_belongs_to_company(branch, company)
	validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)


@frappe.whitelist()
def search_retailedge_bank_accounts(
	company: str,
	branch: str = "",
	txt: str = "",
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	"""Return company-wide plus branch-specific Bank Accounts for RetailEdge selectors."""
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	txt = str(txt or "").strip()
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	if not company or not has_doctype(BANK_ACCOUNT_DOCTYPE):
		return []
	if not frappe.has_permission(BANK_ACCOUNT_DOCTYPE, "read"):
		frappe.throw(_("You do not have permission to view Bank Accounts."), frappe.PermissionError)
	if branch:
		_assert_branch_belongs_to_company(branch, company)
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)

	fields = ["name", "account", "account_name", "bank", "bank_account_no", "company", "disabled", "is_company_account"]
	if has_field(BANK_ACCOUNT_DOCTYPE, BRANCH_FIELD):
		fields.append(BRANCH_FIELD)

	rows: list[Any] = []
	seen: set[str] = set()
	for branch_filter in _bank_account_branch_filters(branch):
		filters: dict[str, Any] = {
			"company": company,
			"is_company_account": 1,
			"disabled": 0,
		}
		filters.update(branch_filter)
		or_filters = _bank_account_text_filters(txt)
		for row in frappe.get_list(
			BANK_ACCOUNT_DOCTYPE,
			filters=filters,
			or_filters=or_filters or None,
			fields=fields,
			order_by="is_default desc, bank asc, account_name asc, name asc",
			limit_page_length=min(MAX_SEARCH_SCAN, max(limit * 3, limit)),
		):
			if row.name in seen:
				continue
			seen.add(row.name)
			rows.append(row)

	rows.sort(key=lambda row: (0 if not str(row.get(BRANCH_FIELD) or "").strip() else 1, str(row.bank or ""), str(row.account_name or row.name)))
	return [_bank_account_option(row) for row in rows[:limit]]


def resolve_retailedge_bank_account(*, company: str, branch: str = "", bank_account: str) -> dict[str, Any]:
	"""Resolve one permitted Bank Account to its ERPNext Bank ledger account."""
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	bank_account = str(bank_account or "").strip()
	if not company or not bank_account:
		frappe.throw(_("Company and Bank Account are required."))
	if not frappe.db.exists(BANK_ACCOUNT_DOCTYPE, bank_account):
		frappe.throw(_("Bank Account {0} does not exist.").format(bank_account))
	if not frappe.has_permission(BANK_ACCOUNT_DOCTYPE, "read", doc=bank_account):
		frappe.throw(_("You do not have permission to use Bank Account {0}.").format(bank_account), frappe.PermissionError)

	fields = ["name", "account", "account_name", "bank", "bank_account_no", "company", "disabled", "is_company_account"]
	if has_field(BANK_ACCOUNT_DOCTYPE, BRANCH_FIELD):
		fields.append(BRANCH_FIELD)
	row = frappe.db.get_value(BANK_ACCOUNT_DOCTYPE, bank_account, fields, as_dict=True)
	if not row or row.company != company or not cint(row.is_company_account) or cint(row.disabled):
		frappe.throw(_("Bank Account {0} is not an enabled company Bank Account for {1}.").format(bank_account, company))
	if not row.account:
		frappe.throw(_("Bank Account {0} is not linked to an ERPNext Bank ledger account.").format(bank_account))

	configured_branch = str(row.get(BRANCH_FIELD) or "").strip()
	if configured_branch:
		if not branch or configured_branch != branch:
			frappe.throw(
				_("Bank Account {0} is restricted to branch {1} and is not available in the current branch.").format(
					bank_account, configured_branch
				),
				frappe.PermissionError,
			)
		validate_user_branch_access(configured_branch, user=frappe.session.user, company=company, throw=True)
	elif branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)

	_account_must_be_company_bank_account(row.account, company)
	return {
		"bank_account": row.name,
		"account": row.account,
		"account_name": row.account_name or row.name,
		"bank": row.bank,
		"bank_account_no": row.bank_account_no,
		"branch": configured_branch,
		"scope": "Branch" if configured_branch else "All Branches",
	}


def validate_cash_deposit_bank_destination(doc, method=None):
	"""Enforce Bank Account branch policy on RetailEdge cashier deposit Payment Entries."""
	if getattr(doc, "doctype", None) != "Payment Entry":
		return
	if getattr(doc, "retailedge_cash_custody_type", None) != "Cash Deposit":
		return
	company = str(getattr(doc, "company", None) or "").strip()
	branch = str(getattr(doc, "retailedge_branch", None) or "").strip()
	paid_to = str(getattr(doc, "paid_to", None) or "").strip()
	if not company or not paid_to:
		frappe.throw(_("RetailEdge cash deposits require Company and destination Bank account."))

	filters = {
		"company": company,
		"is_company_account": 1,
		"disabled": 0,
		"account": paid_to,
	}
	bank_account = frappe.db.get_value(BANK_ACCOUNT_DOCTYPE, filters, "name")
	if not bank_account:
		frappe.throw(
			_("Destination {0} must be linked to an enabled ERPNext company Bank Account before it can receive cashier deposits.").format(
				paid_to
			)
		)
	resolve_retailedge_bank_account(company=company, branch=branch, bank_account=bank_account)


def _bank_account_branch_filters(branch: str) -> list[dict[str, Any]]:
	if not has_field(BANK_ACCOUNT_DOCTYPE, BRANCH_FIELD):
		return [{}]
	filters: list[dict[str, Any]] = [{BRANCH_FIELD: ["in", ["", None]]}]
	if branch:
		filters.append({BRANCH_FIELD: branch})
	return filters


def _bank_account_text_filters(txt: str) -> dict[str, Any]:
	if not txt:
		return {}
	pattern = f"%{txt}%"
	or_filters: dict[str, Any] = {
		"name": ["like", pattern],
		"account_name": ["like", pattern],
		"bank": ["like", pattern],
		"bank_account_no": ["like", pattern],
		"account": ["like", pattern],
	}
	if has_field(BANK_ACCOUNT_DOCTYPE, BRANCH_FIELD):
		or_filters[BRANCH_FIELD] = ["like", pattern]
	return or_filters


def _bank_account_option(row) -> dict[str, Any]:
	branch = str(row.get(BRANCH_FIELD) or "").strip()
	account_no = str(row.bank_account_no or "").strip()
	masked_no = f"••••{account_no[-4:]}" if account_no else ""
	description_parts = [str(row.bank or "").strip(), masked_no, branch or _("All Branches")]
	return {
		"value": row.name,
		"label": row.account_name or row.name,
		"description": " · ".join(part for part in description_parts if part),
		"account": row.account,
		"bank": row.bank,
		"branch": branch,
		"scope": "Branch" if branch else "All Branches",
	}


def _assert_branch_belongs_to_company(branch: str, company: str) -> None:
	if not has_doctype("Branch") or not frappe.db.exists("Branch", branch):
		frappe.throw(_("Branch {0} does not exist.").format(branch))
	if has_field("Branch", "company"):
		branch_company = frappe.db.get_value("Branch", branch, "company")
		if branch_company and branch_company != company:
			frappe.throw(_("Branch {0} does not belong to Company {1}.").format(branch, company))


def _account_must_be_company_bank_account(account: str, company: str) -> None:
	if not frappe.db.exists("Account", account):
		frappe.throw(_("Linked Bank ledger Account {0} does not exist.").format(account))
	if not frappe.has_permission("Account", "read", doc=account):
		frappe.throw(_("You do not have permission to use linked Bank ledger Account {0}.").format(account), frappe.PermissionError)
	fields = ["company", "is_group", "account_type"]
	if has_field("Account", "disabled"):
		fields.append("disabled")
	row = frappe.db.get_value("Account", account, fields, as_dict=True)
	if not row or row.company != company or cint(row.is_group) or row.account_type != "Bank" or cint(row.get("disabled")):
		frappe.throw(_("Linked Account {0} must be an enabled posting Bank account for Company {1}.").format(account, company))
