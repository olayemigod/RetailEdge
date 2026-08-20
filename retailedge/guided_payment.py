from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt, getdate, nowdate

from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account
from erpnext.accounts.doctype.payment_entry.payment_entry import get_party_details, get_reference_details

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
MAX_REFERENCES = 20

PAYMENT_INTENTS: dict[str, dict[str, str]] = {
	"receive-customer-payment": {
		"title": "Receive Customer Payment",
		"payment_type": "Receive",
		"party_type": "Customer",
		"party_label": "Customer",
		"reference_doctype": "Sales Invoice",
		"reference_label": "Sales Invoice",
	},
	"pay-supplier": {
		"title": "Pay Supplier",
		"payment_type": "Pay",
		"party_type": "Supplier",
		"party_label": "Supplier",
		"reference_doctype": "Purchase Invoice",
		"reference_label": "Purchase Invoice",
	},
}


@frappe.whitelist()
def get_simple_payment_context(intent: str) -> dict[str, Any]:
	config = _get_intent(intent)
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
		frappe.throw(_("Set a default Company before creating a Payment Entry."))
	_assert_read_permission("Company", company)
	if branch:
		validate_user_branch_access(branch, user=user, company=company, throw=True)

	return {
		"intent": intent,
		"title": _(config["title"]),
		"subtitle": _(
			"Create a standard ERPNext Payment Entry draft and allocate it to outstanding invoices."
		),
		"submit_label": _("Save Draft"),
		"full_form_doctype": PAYMENT_ENTRY_DOCTYPE,
		"payment_type": config["payment_type"],
		"party_type": config["party_type"],
		"party_label": _(config["party_label"]),
		"reference_doctype": config["reference_doctype"],
		"reference_label": _(config["reference_label"]),
		"defaults": {
			"company": company,
			"branch": branch or "",
			"posting_date": nowdate(),
			"party": "",
			"mode_of_payment": "",
			"amount": "",
			"reference_no": "",
			"reference_date": nowdate(),
			"remarks": "",
			"references": [{"reference_name": "", "outstanding_amount": "", "allocated_amount": ""}],
		},
		"capabilities": {
			"branch_enabled": bool(has_doctype("Branch")),
			"native_form_fallback": True,
		},
		"limits": {"link_results": MAX_LINK_RESULTS, "max_references": MAX_REFERENCES},
	}


@frappe.whitelist()
def search_simple_payment_options(
	intent: str,
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	config = _get_intent(intent)
	_assert_can_create_payment_entry()
	values = _coerce_values(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	branch = values.get("branch") or ""
	party = values.get("party") or ""

	if fieldname == "party":
		return search_link(
			config["party_type"],
			txt or "",
			page_length=limit,
			reference_doctype=PAYMENT_ENTRY_DOCTYPE,
			link_fieldname="party",
		)
	if fieldname == "mode_of_payment":
		return search_link(
			"Mode of Payment",
			txt or "",
			page_length=limit,
			reference_doctype=PAYMENT_ENTRY_DOCTYPE,
			link_fieldname="mode_of_payment",
		)
	if fieldname == "branch":
		if not has_doctype("Branch"):
			return []
		return search_link(
			"Branch",
			txt or "",
			filters=_branch_search_filters(company=company, user=frappe.session.user),
			page_length=limit,
			reference_doctype=PAYMENT_ENTRY_DOCTYPE,
			link_fieldname="retailedge_branch",
		)
	if fieldname == "reference_name":
		if not party:
			return []
		return _search_outstanding_references(
			config=config,
			company=company,
			branch=branch,
			party=party,
			txt=txt or "",
			limit=limit,
		)
	frappe.throw(_("Unsupported Simple Payment search field: {0}").format(fieldname))
	return []


@frappe.whitelist()
def get_simple_payment_mode_details(intent: str, company: str, mode_of_payment: str) -> dict[str, Any]:
	_get_intent(intent)
	_assert_can_create_payment_entry()
	_assert_read_permission("Company", company)
	_assert_read_permission("Mode of Payment", mode_of_payment)
	account = get_default_bank_cash_account(
		company,
		mode_of_payment=mode_of_payment,
		fetch_balance=False,
	)
	if not account or not account.get("account"):
		frappe.throw(
			_("Mode of Payment {0} has no company Bank/Cash account configured.").format(mode_of_payment)
		)
	_assert_read_permission("Account", account.account)
	if account.account_type not in {"Bank", "Cash"}:
		frappe.throw(_("Mode of Payment {0} must resolve to a Bank or Cash account.").format(mode_of_payment))
	return {
		"account": account.account,
		"account_type": account.account_type,
		"account_currency": account.account_currency,
		"reference_required": account.account_type == "Bank",
	}


@frappe.whitelist()
def get_simple_payment_reference_details(
	intent: str,
	company: str,
	party: str,
	reference_name: str,
	branch: str | None = None,
) -> dict[str, Any]:
	config = _get_intent(intent)
	_assert_can_create_payment_entry()
	_assert_read_permission(config["party_type"], party)
	return _get_reference_snapshot(
		config=config,
		company=company,
		party=party,
		reference_name=reference_name,
		branch=branch or "",
	)


@frappe.whitelist(methods=["POST"])
def create_simple_payment_draft(intent: str, values: dict | str | None = None) -> dict[str, Any]:
	config = _get_intent(intent)
	_assert_can_create_payment_entry()
	values = _coerce_values(values)
	user = frappe.session.user
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	if not company:
		frappe.throw(_("Company is required."))
	_assert_read_permission("Company", company)
	company_currency = frappe.db.get_value("Company", company, "default_currency")
	if not company_currency:
		frappe.throw(_("Company {0} has no default currency configured.").format(company))

	branch = values.get("branch") or ""
	if branch:
		validate_user_branch_access(branch, user=user, company=company, throw=True)

	party = str(values.get("party") or "").strip()
	if not party:
		frappe.throw(_("{0} is required.").format(_(config["party_label"])))
	_assert_read_permission(config["party_type"], party)

	posting_date = getdate(values.get("posting_date") or nowdate())
	party_details = get_party_details(company, config["party_type"], party, posting_date)
	party_account = party_details.get("party_account")
	party_currency = party_details.get("party_account_currency")
	if not party_account:
		frappe.throw(_("No party account could be resolved for {0}.").format(party))
	_assert_read_permission("Account", party_account)

	mode_of_payment = str(values.get("mode_of_payment") or "").strip()
	if not mode_of_payment:
		frappe.throw(_("Mode of Payment is required."))
	mode_details = get_simple_payment_mode_details(intent, company, mode_of_payment)
	bank_account = mode_details["account"]
	bank_currency = mode_details["account_currency"]
	if party_currency != company_currency or bank_currency != company_currency:
		frappe.throw(
			_(
				"Simple Payment currently supports company-currency payments only. Use the full Payment Entry form for multi-currency payments."
			)
		)

	amount = flt(values.get("amount"))
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero."))

	references = _normalise_references(values.get("references"))
	snapshots: list[dict[str, Any]] = []
	total_allocated = 0.0
	resolved_branches: set[str] = set()
	for reference in references:
		snapshot = _get_reference_snapshot(
			config=config,
			company=company,
			party=party,
			reference_name=reference["reference_name"],
			branch=branch,
		)
		allocated_amount = flt(reference["allocated_amount"])
		if allocated_amount <= 0:
			frappe.throw(_("Allocated Amount must be greater than zero for {0}.").format(reference["reference_name"]))
		if allocated_amount > flt(snapshot["outstanding_amount"]):
			frappe.throw(
				_("Allocated Amount for {0} cannot exceed the latest outstanding amount {1}.").format(
					reference["reference_name"], snapshot["outstanding_amount"]
				)
			)
		total_allocated += allocated_amount
		snapshot["allocated_amount"] = allocated_amount
		snapshots.append(snapshot)
		if snapshot.get("branch"):
			resolved_branches.add(snapshot["branch"])

	if total_allocated > amount:
		frappe.throw(_("Total allocated amount cannot exceed the payment amount."))
	if len(resolved_branches) > 1:
		frappe.throw(_("All selected invoices must belong to the same RetailEdge Branch."))
	if branch and resolved_branches and branch not in resolved_branches:
		frappe.throw(_("Selected invoices do not belong to Branch {0}.").format(branch))

	doc = frappe.new_doc(PAYMENT_ENTRY_DOCTYPE)
	doc.payment_type = config["payment_type"]
	doc.company = company
	doc.posting_date = posting_date
	doc.party_type = config["party_type"]
	doc.party = party
	doc.mode_of_payment = mode_of_payment
	doc.paid_amount = amount
	doc.received_amount = amount
	if config["payment_type"] == "Receive":
		doc.paid_from = party_account
		doc.paid_to = bank_account
	else:
		doc.paid_from = bank_account
		doc.paid_to = party_account
	if branch:
		doc.branch = branch

	if mode_details["reference_required"]:
		reference_no = str(values.get("reference_no") or "").strip()
		if not reference_no:
			frappe.throw(_("Reference No is required for Bank payments."))
		doc.reference_no = reference_no
		doc.reference_date = getdate(values.get("reference_date") or posting_date)

	if values.get("remarks"):
		doc.custom_remarks = 1
		doc.remarks = str(values.get("remarks")).strip()

	for snapshot in snapshots:
		doc.append(
			"references",
			{
				"reference_doctype": config["reference_doctype"],
				"reference_name": snapshot["reference_name"],
				"due_date": snapshot.get("due_date"),
				"total_amount": snapshot.get("total_amount"),
				"outstanding_amount": snapshot.get("outstanding_amount"),
				"allocated_amount": snapshot["allocated_amount"],
			},
		)

	# Insert as the current user. PaymentEntry.validate owns party account completion,
	# exchange rates, current outstanding revalidation, totals, unallocated amount and ledger safety.
	doc.insert()
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"payment_type": doc.payment_type,
		"party_type": doc.party_type,
		"party": doc.party,
		"company": doc.company,
		"branch": getattr(doc, "retailedge_branch", None) or branch,
		"paid_amount": doc.paid_amount,
		"unallocated_amount": getattr(doc, "unallocated_amount", None),
		"route": f"/app/payment-entry/{doc.name}",
	}


def _search_outstanding_references(
	*,
	config: dict[str, str],
	company: str,
	branch: str,
	party: str,
	txt: str,
	limit: int,
) -> list[dict[str, Any]]:
	_assert_read_permission(config["party_type"], party)
	filters: dict[str, Any] = {
		"company": company,
		config["party_type"].lower(): party,
		"docstatus": 1,
		"outstanding_amount": [">", 0],
	}
	if txt:
		filters["name"] = ["like", f"%{txt}%"]
	if branch and has_field(config["reference_doctype"], "retailedge_branch"):
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)
		filters["retailedge_branch"] = branch

	fields = ["name", "posting_date", "outstanding_amount", "currency"]
	if has_field(config["reference_doctype"], "due_date"):
		fields.append("due_date")
	rows = frappe.get_list(
		config["reference_doctype"],
		filters=filters,
		fields=fields,
		order_by="due_date asc, posting_date asc, name asc" if "due_date" in fields else "posting_date asc, name asc",
		limit_page_length=limit,
	)
	return [
		{
			"value": row.name,
			"label": row.name,
			"description": _reference_description(row),
		}
		for row in rows
	]


def _get_reference_snapshot(
	*,
	config: dict[str, str],
	company: str,
	party: str,
	reference_name: str,
	branch: str,
) -> dict[str, Any]:
	reference_doctype = config["reference_doctype"]
	_assert_read_permission(reference_doctype, reference_name)
	party_field = config["party_type"].lower()
	fields = ["company", party_field, "docstatus", "currency", "payment_terms_template"]
	if has_field(reference_doctype, "retailedge_branch"):
		fields.append("retailedge_branch")
	row = frappe.db.get_value(reference_doctype, reference_name, fields, as_dict=True)
	if not row or row.company != company or row.get(party_field) != party or cint(row.docstatus) != 1:
		frappe.throw(_("{0} {1} is not a submitted outstanding invoice for this party and company.").format(reference_doctype, reference_name))

	if row.payment_terms_template and frappe.db.get_value(
		"Payment Terms Template",
		row.payment_terms_template,
		"allocate_payment_based_on_payment_terms",
	):
		frappe.throw(
			_("{0} uses payment-term allocation. Use the full Payment Entry form for this invoice.").format(reference_name)
		)

	company_currency = frappe.db.get_value("Company", company, "default_currency")
	if row.currency and row.currency != company_currency:
		frappe.throw(
			_("{0} is in {1}. Use the full Payment Entry form for multi-currency invoices.").format(
				reference_name, row.currency
			)
		)

	party_details = get_party_details(company, config["party_type"], party, nowdate())
	details = get_reference_details(
		reference_doctype,
		reference_name,
		party_details.get("party_account_currency"),
		config["party_type"],
		party,
	)
	outstanding = flt(details.get("outstanding_amount"))
	if outstanding <= 0:
		frappe.throw(_("{0} has no positive outstanding amount.").format(reference_name))

	reference_branch = row.get("retailedge_branch") if "retailedge_branch" in row else None
	if branch and reference_branch and reference_branch != branch:
		frappe.throw(_("{0} belongs to Branch {1}, not Branch {2}.").format(reference_name, reference_branch, branch))
	return {
		"reference_name": reference_name,
		"outstanding_amount": outstanding,
		"total_amount": flt(details.get("total_amount")),
		"due_date": details.get("due_date"),
		"branch": reference_branch,
		"currency": row.currency or company_currency,
	}


def _normalise_references(references: Any) -> list[dict[str, Any]]:
	if isinstance(references, str):
		references = frappe.parse_json(references)
	if not isinstance(references, list) or not references:
		frappe.throw(_("Add at least one outstanding invoice."))
	if len(references) > MAX_REFERENCES:
		frappe.throw(_("A Simple Payment can contain at most {0} invoice references.").format(MAX_REFERENCES))

	result: list[dict[str, Any]] = []
	seen: set[str] = set()
	for index, row in enumerate(references, start=1):
		if not isinstance(row, dict):
			frappe.throw(_("Payment reference row {0} is invalid.").format(index))
		name = str(row.get("reference_name") or "").strip()
		if not name:
			frappe.throw(_("Invoice is required on reference row {0}.").format(index))
		if name in seen:
			frappe.throw(_("Invoice {0} is selected more than once.").format(name))
		seen.add(name)
		result.append({"reference_name": name, "allocated_amount": flt(row.get("allocated_amount"))})
	return result


def _branch_search_filters(company: str, user: str) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	if company and has_field("Branch", "company"):
		filters["company"] = company
	if user_has_global_branch_access(user=user):
		return filters
	allowed = get_user_allowed_branches(user=user, company=company or None).get("branches") or []
	if allowed:
		filters["name"] = ["in", allowed]
	return filters


def _reference_description(row: frappe._dict) -> str:
	parts = []
	if row.get("due_date"):
		parts.append(_("Due {0}").format(row.due_date))
	parts.append(_("Outstanding {0} {1}").format(row.get("currency") or "", row.outstanding_amount))
	return " · ".join(parts)


def _get_intent(intent: str) -> dict[str, str]:
	config = PAYMENT_INTENTS.get(intent)
	if not config:
		frappe.throw(_("Unsupported Simple Payment action."))
	return config


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
		return dict(values)
	frappe.throw(_("Invalid Simple Payment values."))
	return {}
