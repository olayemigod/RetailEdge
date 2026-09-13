from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, get_first_day, getdate, now_datetime, today

from retailedge.branch_profile import (
	get_enabled_branch_profiles,
	get_exact_branch_profile,
	has_enabled_branch_profiles,
)
from retailedge.operating_context import get_operational_branch_scope
from retailedge.utils.settings import get_retailedge_settings

BUSINESS_EXPENSE_DOCTYPE = "RetailEdge Business Expense"
CATEGORY_DOCTYPE = "RetailEdge Expense Category"
MAX_LINK_RESULTS = 20
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_DATE_RANGE_DAYS = 366
BUSINESS_EXPENSE_SORT_FIELDS = {
	"expense_date",
	"expense_category",
	"payee_name",
	"branch",
	"expense_status",
	"ledger_status",
	"amount",
	"modified",
	"name",
}
BUSINESS_EXPENSE_SORT_DIRECTIONS = {"asc", "desc"}
DEFAULT_BUSINESS_EXPENSE_ORDER = "expense_date desc, modified desc, name desc"

BUSINESS_EXPENSE_READ_ROLES = {
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}

BUSINESS_EXPENSE_REVIEWER_ROLES = {
	"System Manager",
	"Accounts Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
}

BUSINESS_EXPENSE_ALLOWED_PROCESSES = {
	"Approval Required",
	"Direct Posting",
}

BUSINESS_EXPENSE_STATUS_ORDER = (
	"Draft",
	"Submitted",
	"Approved",
	"Rejected",
	"Pending Ledger",
	"Posted",
	"Reversed",
	"Cancelled",
)
BUSINESS_EXPENSE_STATUSES = set(BUSINESS_EXPENSE_STATUS_ORDER)


def get_business_expense_settings() -> dict[str, Any]:
	try:
		settings = get_retailedge_settings()
	except Exception:
		return {
			"enabled": False,
			"process": "Approval Required",
			"require_attachment": False,
			"accounting_posting_enabled": False,
			"posting_document_type": "Journal Entry",
			"posting_workflow_state": "",
			"default_payment_account": "",
		}

	process = str(
		getattr(settings, "business_expense_process", None)
		or "Approval Required"
	).strip()
	if process not in BUSINESS_EXPENSE_ALLOWED_PROCESSES:
		process = "Approval Required"
	return {
		"enabled": bool(cint(getattr(settings, "enable_business_expenses", 0))),
		"process": process,
		"require_attachment": bool(
			cint(getattr(settings, "require_business_expense_attachment", 0))
		),
		"accounting_posting_enabled": bool(
			cint(getattr(settings, "enable_business_expense_accounting_posting", 0))
		),
		"posting_document_type": str(
			getattr(settings, "business_expense_posting_document_type", None)
			or "Journal Entry"
		),
		"posting_workflow_state": str(
			getattr(settings, "business_expense_posting_workflow_state", None)
			or ""
		).strip(),
		"default_payment_account": str(
			getattr(settings, "default_business_expense_payment_account", None)
			or ""
		).strip(),
	}


def user_is_business_expense_reviewer(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return bool(
		set(frappe.get_roles(user)).intersection(BUSINESS_EXPENSE_REVIEWER_ROLES)
	)


@frappe.whitelist()
def get_business_expense_context() -> dict[str, Any]:
	_assert_feature_enabled()
	user = frappe.session.user
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	if company:
		_assert_company_access(company)
	branch = ""
	if company:
		branch = resolve_business_expense_branch(
			company=company,
			branch=str(
				frappe.defaults.get_user_default("RetailEdge Branch")
				or frappe.defaults.get_user_default("Branch")
				or ""
			).strip(),
			require_when_restricted=False,
		)
	settings = get_business_expense_settings()
	return {
		"title": _("Business Expenses"),
		"subtitle": _(
			"Record non-POS business spending with evidence, approval and accounting controls."
		),
		"default_values": {
			"company": company,
			"branch": branch,
			"expense_date": today(),
			"expense_category": "",
			"amount": "",
			"description": "",
			"payee_type": "Other",
			"supplier": "",
			"payee_name": "",
			"reference_no": "",
			"attachment": "",
			"payment_account": settings["default_payment_account"],
			"cost_center": "",
			"project": "",
		},
		"default_filters": {
			"company": company,
			"branch": branch,
			"from_date": str(get_first_day(today())),
			"to_date": today(),
			"expense_category": "",
			"expense_status": "",
			"search_text": "",
			"page_size": DEFAULT_PAGE_SIZE,
		},
		"statuses": list(BUSINESS_EXPENSE_STATUS_ORDER),
		"settings": settings,
		"capabilities": {
			"can_create": bool(
				frappe.has_permission(BUSINESS_EXPENSE_DOCTYPE, "create")
			),
			"can_review": user_is_business_expense_reviewer(user),
		},
		"limits": {"link_results": MAX_LINK_RESULTS},
	}


@frappe.whitelist()
def search_business_expense_options(
	kind: str,
	txt: str = "",
	company: str = "",
	branch: str = "",
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_feature_enabled()
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(
		company or frappe.defaults.get_user_default("Company") or ""
	).strip()
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))

	if kind == "company":
		return _search_companies(txt=txt, limit=limit)
	if not company:
		frappe.throw(_("Company is required."))
	_assert_company_access(company)

	if kind == "branch":
		return _search_branches(txt=txt, company=company, limit=limit)
	if kind == "expense_category":
		return _search_categories(txt=txt, company=company, limit=limit)
	if kind == "payment_account":
		return _search_payment_accounts(txt=txt, company=company, limit=limit)
	if kind == "cost_center":
		return _search_cost_centers(txt=txt, company=company, limit=limit)
	if kind == "project":
		return _search_projects(txt=txt, company=company, limit=limit)
	if kind == "supplier":
		return _search_suppliers(txt=txt, limit=limit)
	frappe.throw(_("Unsupported Business Expense search type."))
	return []


@frappe.whitelist()
def get_business_expense_category_defaults(
	expense_category: str,
	company: str,
) -> dict[str, Any]:
	_assert_feature_enabled()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	_assert_company_access(company)
	expense_category = str(expense_category or "").strip()
	if not expense_category:
		return {"expense_account": "", "cost_center": ""}
	if not frappe.db.exists(CATEGORY_DOCTYPE, expense_category):
		frappe.throw(_("Expense Category {0} does not exist.").format(expense_category))
	if not frappe.has_permission(CATEGORY_DOCTYPE, "read", doc=expense_category):
		frappe.throw(
			_("You do not have permission to use this Expense Category."),
			frappe.PermissionError,
		)
	row = frappe.db.get_value(
		CATEGORY_DOCTYPE,
		expense_category,
		["company", "is_active", "expense_account", "default_cost_center", "description"],
		as_dict=True,
	)
	if not row or not cint(row.is_active):
		frappe.throw(_("Expense Category {0} is inactive.").format(expense_category))
	if row.company and row.company != company:
		frappe.throw(_("Expense Category {0} belongs to another Company.").format(expense_category))
	if not row.expense_account:
		frappe.throw(_("Expense Category {0} has no Expense Account configured.").format(expense_category))
	_validate_expense_account(row.expense_account, company)
	if row.default_cost_center:
		_validate_cost_center(row.default_cost_center, company)
	return {
		"expense_account": row.expense_account,
		"cost_center": row.default_cost_center or "",
		"description": row.description or "",
	}


def _normalise_business_expense_sort(
	sort: dict[str, Any] | str | None,
) -> tuple[dict[str, str] | None, str]:
	if isinstance(sort, str):
		try:
			sort = frappe.parse_json(sort)
		except Exception:
			return None, DEFAULT_BUSINESS_EXPENSE_ORDER
	if not isinstance(sort, dict):
		return None, DEFAULT_BUSINESS_EXPENSE_ORDER

	field = str(sort.get("field") or sort.get("fieldname") or sort.get("key") or "").strip()
	direction = str(sort.get("direction") or sort.get("order") or "").strip().lower()
	if field not in BUSINESS_EXPENSE_SORT_FIELDS or direction not in BUSINESS_EXPENSE_SORT_DIRECTIONS:
		return None, DEFAULT_BUSINESS_EXPENSE_ORDER

	order_parts = [f"{field} {direction}"]
	if field != "modified":
		order_parts.append("modified desc")
	if field != "name":
		order_parts.append("name desc")
	return {"field": field, "direction": direction}, ", ".join(order_parts)


@frappe.whitelist()
def get_business_expenses(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
	sort: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	_assert_feature_enabled()
	filters = _coerce_values(filters)
	query_filters, or_filters, scope = _build_business_expense_list_filters(filters)
	page = max(1, cint(page) or 1)
	page_size = max(1, min(cint(page_size) or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE))
	normalized_sort, order_by = _normalise_business_expense_sort(sort)

	aggregate = frappe.get_list(
		BUSINESS_EXPENSE_DOCTYPE,
		filters=query_filters,
		or_filters=or_filters or None,
		fields=[
			{"COUNT": "name", "as": "count"},
			{"SUM": "amount", "as": "total_amount"},
		],
		limit_page_length=1,
	)
	summary_row = aggregate[0] if aggregate else frappe._dict(count=0, total_amount=0)
	total_rows = cint(summary_row.count)
	total_pages = max(1, ceil(total_rows / page_size)) if total_rows else 1
	if page > total_pages:
		page = total_pages

	rows = frappe.get_list(
		BUSINESS_EXPENSE_DOCTYPE,
		filters=query_filters,
		or_filters=or_filters or None,
		fields=[
			"name",
			"expense_date",
			"company",
			"branch",
			"expense_category",
			"amount",
			"payee_type",
			"supplier",
			"payee_name",
			"reference_no",
			"payment_account",
			"cost_center",
			"project",
			"expense_status",
			"ledger_status",
			"posting_ready",
			"posting_reference_type",
			"posting_reference",
			"requested_by",
			"modified",
		],
		order_by=order_by,
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
	)
	return {
		"rows": [dict(row) for row in rows],
		"summary": {
			"count": total_rows,
			"total_amount": flt(summary_row.total_amount),
		},
		"pagination": {
			"page": page,
			"page_size": page_size,
			"total_rows": total_rows,
			"total_pages": total_pages,
			"has_previous": page > 1,
			"has_next": page < total_pages,
		},
		"scope": scope,
		"sort": normalized_sort,
	}


@frappe.whitelist(methods=["POST"])
def create_business_expense_draft(
	values: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	_assert_feature_enabled()
	if not frappe.has_permission(BUSINESS_EXPENSE_DOCTYPE, "create"):
		frappe.throw(
			_("You do not have permission to create Business Expenses."),
			frappe.PermissionError,
		)
	values = _coerce_values(values)
	doc = frappe.new_doc(BUSINESS_EXPENSE_DOCTYPE)
	_apply_business_expense_values(doc, values)
	doc.insert()
	return _business_expense_payload(doc, include_workflow=True)


@frappe.whitelist(methods=["POST"])
def update_business_expense_draft(
	name: str,
	values: dict[str, Any] | str | None = None,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	_assert_feature_enabled()
	doc = _get_business_expense_for_action(name)
	if doc.docstatus != 0:
		frappe.throw(_("Only draft Business Expenses can be edited."))
	if not doc.has_permission("write"):
		frappe.throw(
			_("You do not have permission to edit this Business Expense."),
			frappe.PermissionError,
		)
	_assert_modified(doc, expected_modified)
	_apply_business_expense_values(doc, _coerce_values(values))
	doc.save()
	return _business_expense_payload(doc, include_workflow=True)


@frappe.whitelist(methods=["POST"])
def set_business_expense_attachment(
	name: str,
	file_url: str,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	_assert_feature_enabled()
	doc = _get_business_expense_for_action(name)
	if doc.docstatus != 0:
		frappe.throw(_("Evidence can be changed only while the Business Expense is a draft."))
	if not doc.has_permission("write"):
		frappe.throw(
			_("You do not have permission to attach evidence to this Business Expense."),
			frappe.PermissionError,
		)
	_assert_modified(doc, expected_modified)
	file_url = str(file_url or "").strip()
	if not file_url:
		frappe.throw(_("Uploaded evidence file is required."))
	if not frappe.db.exists(
		"File",
		{
			"file_url": file_url,
			"attached_to_doctype": BUSINESS_EXPENSE_DOCTYPE,
			"attached_to_name": doc.name,
		},
	):
		frappe.throw(_("The uploaded file is not attached to this Business Expense."))
	doc.attachment = file_url
	doc.save()
	return _business_expense_payload(doc, include_workflow=True)


@frappe.whitelist()
def get_business_expense(name: str) -> dict[str, Any]:
	_assert_feature_enabled()
	name = str(name or "").strip()
	if not name:
		frappe.throw(_("Business Expense name is required."))
	doc = frappe.get_doc(BUSINESS_EXPENSE_DOCTYPE, name)
	if not frappe.has_permission(BUSINESS_EXPENSE_DOCTYPE, "read", doc=doc):
		frappe.throw(
			_("You do not have permission to view this Business Expense."),
			frappe.PermissionError,
		)
	return _business_expense_payload(doc, include_workflow=True)


def _apply_business_expense_values(doc, values: dict[str, Any]) -> None:
	for fieldname in (
		"company",
		"branch",
		"expense_date",
		"expense_category",
		"description",
		"payee_type",
		"supplier",
		"payee_name",
		"reference_no",
		"payment_account",
		"cost_center",
		"project",
	):
		if fieldname in values:
			setattr(doc, fieldname, values.get(fieldname) or None)
	if "amount" in values:
		doc.amount = flt(values.get("amount"))
	payee_type = str(getattr(doc, "payee_type", None) or "Other")
	if payee_type == "Supplier":
		doc.payee_name = None
	else:
		doc.supplier = None


def _build_business_expense_list_filters(
	filters: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
	company = str(
		filters.get("company") or frappe.defaults.get_user_default("Company") or ""
	).strip()
	if not company:
		frappe.throw(_("Company is required."))
	_assert_company_access(company)
	query_filters: dict[str, Any] = {"company": company}
	requested_branch = str(filters.get("branch") or "").strip()
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	allowed = [
		str(value).strip()
		for value in dict.fromkeys(scope.get("allowed_branches") or [])
		if str(value or "").strip()
	]
	if requested_branch:
		query_filters["branch"] = resolve_business_expense_branch(
			company=company,
			branch=requested_branch,
			require_when_restricted=True,
		)
	elif scope.get("restricted"):
		query_filters["branch"] = ["in", allowed] if allowed else "__never__"

	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else None
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else None
	if from_date and to_date:
		if from_date > to_date:
			frappe.throw(_("From Date cannot be after To Date."))
		if (to_date - from_date).days + 1 > MAX_DATE_RANGE_DAYS:
			frappe.throw(
				_("Business Expenses supports up to {0} days per request.").format(
					MAX_DATE_RANGE_DAYS
				)
			)
		query_filters["expense_date"] = ["between", [from_date, to_date]]
	elif from_date:
		query_filters["expense_date"] = [">=", from_date]
	elif to_date:
		query_filters["expense_date"] = ["<=", to_date]

	status = str(filters.get("expense_status") or "").strip()
	if status:
		if status not in BUSINESS_EXPENSE_STATUSES:
			frappe.throw(_("Unsupported Business Expense Status."))
		query_filters["expense_status"] = status

	category = str(filters.get("expense_category") or "").strip()
	if category:
		query_filters["expense_category"] = category

	search_text = str(filters.get("search_text") or "").strip()
	or_filters: dict[str, Any] = {}
	if search_text:
		like = f"%{search_text}%"
		or_filters = {
			"name": ["like", like],
			"supplier": ["like", like],
			"payee_name": ["like", like],
			"reference_no": ["like", like],
			"description": ["like", like],
		}

	return query_filters, or_filters, {
		"company": company,
		"branch": requested_branch,
		"restricted": int(bool(scope.get("restricted"))),
		"allowed_branches": allowed,
	}


def _assert_modified(doc, expected_modified: str | None) -> None:
	expected = str(expected_modified or "").strip()
	if not expected:
		return
	try:
		if get_datetime(expected) != get_datetime(doc.modified):
			raise ValueError
	except Exception:
		frappe.throw(
			_("This Business Expense changed after it was loaded. Refresh before continuing."),
			frappe.TimestampMismatchError,
		)


def prepare_business_expense_defaults(doc) -> None:
	settings = get_business_expense_settings()
	if not settings["enabled"]:
		frappe.throw(_("Business Expenses are disabled in RetailEdge Settings."))
	if not getattr(doc, "requested_by", None):
		doc.requested_by = frappe.session.user
	if not getattr(doc, "expense_date", None):
		doc.expense_date = today()
	if not getattr(doc, "company", None):
		doc.company = frappe.defaults.get_user_default("Company") or None
	if not getattr(doc, "payee_type", None):
		doc.payee_type = "Other"
	if not getattr(doc, "expense_status", None):
		doc.expense_status = "Draft"
	if not getattr(doc, "ledger_status", None):
		doc.ledger_status = "Not Applicable"
	if not getattr(doc, "payment_account", None) and settings["default_payment_account"]:
		doc.payment_account = settings["default_payment_account"]
	if getattr(doc, "company", None):
		doc.branch = resolve_business_expense_branch(
			company=doc.company,
			branch=getattr(doc, "branch", None),
			require_when_restricted=False,
		)
	_apply_category_defaults(doc)


def validate_business_expense_document(doc) -> None:
	_assert_posted_business_expense_workflow_terminal(doc)
	settings = get_business_expense_settings()
	if not settings["enabled"]:
		frappe.throw(_("Business Expenses are disabled in RetailEdge Settings."))
	if not getattr(doc, "company", None):
		frappe.throw(_("Company is required."))
	_assert_company_access(doc.company)
	doc.branch = resolve_business_expense_branch(
		company=doc.company,
		branch=getattr(doc, "branch", None),
		require_when_restricted=True,
	)
	if not getattr(doc, "expense_category", None):
		frappe.throw(_("Expense Category is required."))
	_apply_category_defaults(doc)
	if flt(getattr(doc, "amount", 0)) <= 0:
		frappe.throw(_("Amount must be greater than zero."))
	if not getattr(doc, "expense_account", None):
		frappe.throw(
			_("Expense Account could not be resolved from the selected Expense Category.")
		)
	_validate_expense_account(doc.expense_account, doc.company)
	if not getattr(doc, "payment_account", None):
		frappe.throw(_("Paid From account is required."))
	_validate_payment_account(doc.payment_account, doc.company)
	if getattr(doc, "cost_center", None):
		_validate_cost_center(doc.cost_center, doc.company)
	if getattr(doc, "project", None):
		_validate_project(doc.project, doc.company)
	if getattr(doc, "payee_type", None) == "Supplier":
		if not getattr(doc, "supplier", None):
			frappe.throw(_("Supplier is required when Payee Type is Supplier."))
		if not frappe.has_permission("Supplier", "read", doc=doc.supplier):
			frappe.throw(
				_("You do not have permission to use this Supplier."),
				frappe.PermissionError,
		)



def _assert_posted_business_expense_workflow_terminal(doc) -> None:
	if not getattr(doc, "name", None) or getattr(doc, "is_new", lambda: False)():
		return
	previous = frappe.db.get_value(
		BUSINESS_EXPENSE_DOCTYPE,
		doc.name,
		["posting_reference", "workflow_state"],
		as_dict=True,
	)
	if not previous or not previous.posting_reference:
		return
	if str(getattr(doc, "workflow_state", None) or "") != str(
		previous.workflow_state or ""
	):
		frappe.throw(
			_(
				"Posted Business Expenses cannot move to another Workflow State. Use the approved accounting reversal process for corrections."
			)
		)


def prepare_business_expense_for_submit(doc) -> None:
	from retailedge.workflow_readiness import _get_active_workflow

	settings = get_business_expense_settings()
	if settings["require_attachment"] and not getattr(doc, "attachment", None):
		frappe.throw(
			_("Receipt or supporting evidence is required before submitting this Business Expense.")
		)
	if _get_active_workflow(BUSINESS_EXPENSE_DOCTYPE):
		return
	if settings["process"] == "Direct Posting":
		doc.expense_status = "Approved"
		doc.ledger_status = "Pending Ledger"
	else:
		doc.expense_status = "Submitted"
		doc.ledger_status = "Not Applicable"


def prepare_business_expense_for_cancel(doc) -> None:
	if (
		str(getattr(doc, "ledger_status", None) or "") == "Posted"
		or getattr(doc, "posting_reference", None)
	):
		frappe.throw(
			_(
				"Posted Business Expenses cannot be cancelled directly. "
				"Reverse or cancel the linked accounting document using the approved accounting process."
			)
		)
	doc.expense_status = "Cancelled"


def submit_business_expense(name: str) -> dict[str, Any]:
	doc = _get_business_expense_for_action(name)
	if doc.docstatus != 0:
		frappe.throw(_("Only draft Business Expenses can be submitted."))
	if not doc.has_permission("submit"):
		frappe.throw(
			_("You do not have permission to submit this Business Expense."),
			frappe.PermissionError,
		)
	doc.submit()
	return _business_expense_payload(doc, include_workflow=False)


def approve_business_expense(
	name: str,
	remarks: str | None = None,
) -> dict[str, Any]:
	doc = _get_business_expense_for_review(name)
	settings = get_business_expense_settings()
	if settings["process"] != "Approval Required":
		frappe.throw(
			_("This Business Expense does not use the RetailEdge approval fallback.")
		)
	if doc.docstatus != 1 or doc.expense_status != "Submitted":
		frappe.throw(_("Only submitted Business Expenses can be approved."))
	_assert_not_self_approval(doc)
	if not doc.has_permission("write"):
		frappe.throw(
			_("You do not have permission to approve this Business Expense."),
			frappe.PermissionError,
		)
	doc.expense_status = "Approved"
	doc.ledger_status = "Pending Ledger"
	doc.approved_by = frappe.session.user
	doc.approved_on = now_datetime()
	doc.rejected_by = None
	doc.rejected_on = None
	doc.review_remarks = remarks
	doc.save()
	return _business_expense_payload(doc, include_workflow=False)


def reject_business_expense(
	name: str,
	remarks: str | None = None,
) -> dict[str, Any]:
	if not str(remarks or "").strip():
		frappe.throw(_("Remarks are required when rejecting a Business Expense."))
	doc = _get_business_expense_for_review(name)
	if doc.docstatus != 1 or doc.expense_status != "Submitted":
		frappe.throw(_("Only submitted Business Expenses can be rejected."))
	_assert_not_self_approval(doc)
	if not doc.has_permission("write"):
		frappe.throw(
			_("You do not have permission to reject this Business Expense."),
			frappe.PermissionError,
		)
	doc.expense_status = "Rejected"
	doc.ledger_status = "Not Applicable"
	doc.rejected_by = frappe.session.user
	doc.rejected_on = now_datetime()
	doc.approved_by = None
	doc.approved_on = None
	doc.review_remarks = remarks
	doc.save()
	return _business_expense_payload(doc, include_workflow=False)


def reopen_business_expense(
	name: str,
	remarks: str | None = None,
) -> dict[str, Any]:
	doc = _get_business_expense_for_review(name)
	if doc.docstatus != 1 or doc.expense_status != "Rejected":
		frappe.throw(_("Only rejected Business Expenses can be reopened."))
	if not doc.has_permission("write"):
		frappe.throw(
			_("You do not have permission to reopen this Business Expense."),
			frappe.PermissionError,
		)
	doc.expense_status = "Submitted"
	doc.ledger_status = "Not Applicable"
	doc.rejected_by = None
	doc.rejected_on = None
	doc.review_remarks = remarks
	doc.save()
	return _business_expense_payload(doc, include_workflow=False)


def resolve_business_expense_branch(
	*,
	company: str,
	branch: str | None,
	require_when_restricted: bool,
) -> str:
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	if not company:
		return branch
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	restricted = bool(scope.get("restricted"))
	allowed = sorted(
		str(value).strip()
		for value in dict.fromkeys(scope.get("allowed_branches") or [])
		if str(value or "").strip()
	)
	if restricted:
		if branch:
			if branch not in allowed:
				frappe.throw(
					_("You do not have active RetailEdge Branch access to {0}.").format(
						branch
					),
					frappe.PermissionError,
				)
		else:
			if len(allowed) == 1:
				branch = allowed[0]
			elif require_when_restricted and len(allowed) > 1:
				frappe.throw(
					_("Choose a Branch before recording this Business Expense.")
				)
			elif require_when_restricted and not allowed:
				frappe.throw(
					_("You do not have an active RetailEdge Branch for this Company."),
					frappe.PermissionError,
				)
	if branch:
		_validate_branch_company_pair(company=company, branch=branch)
	return branch


def _apply_category_defaults(doc) -> None:
	category_name = str(getattr(doc, "expense_category", None) or "").strip()
	if not category_name:
		return
	if not frappe.db.exists(CATEGORY_DOCTYPE, category_name):
		frappe.throw(
			_("Expense Category {0} does not exist.").format(category_name)
		)
	if not frappe.has_permission(CATEGORY_DOCTYPE, "read", doc=category_name):
		frappe.throw(
			_("You do not have permission to use this Expense Category."),
			frappe.PermissionError,
		)
	category = frappe.db.get_value(
		CATEGORY_DOCTYPE,
		category_name,
		["company", "is_active", "expense_account", "default_cost_center"],
		as_dict=True,
	)
	if not category or not cint(category.is_active):
		frappe.throw(_("Expense Category {0} is inactive.").format(category_name))
	if category.company and doc.company and category.company != doc.company:
		frappe.throw(
			_("Expense Category {0} belongs to another Company.").format(
				category_name
			)
		)
	if category.expense_account:
		doc.expense_account = category.expense_account
	if category.default_cost_center and not getattr(doc, "cost_center", None):
		doc.cost_center = category.default_cost_center


def _validate_branch_company_pair(*, company: str, branch: str) -> None:
	if not frappe.db.exists("Branch", branch):
		frappe.throw(_("Branch {0} does not exist.").format(branch))
	if has_enabled_branch_profiles(company=company):
		profile = get_exact_branch_profile(
			company=company,
			branch=branch,
			active_only=True,
		)
		if not profile:
			frappe.throw(
				_("Branch {0} is not configured for Company {1}.").format(
					branch,
					company,
				)
			)


def _validate_expense_account(account: str, company: str) -> None:
	row = frappe.db.get_value(
		"Account",
		account,
		["company", "root_type", "is_group", "disabled"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Expense Account {0} does not exist.").format(account))
	if row.company != company:
		frappe.throw(_("Expense Account belongs to another Company."))
	if row.root_type != "Expense" or cint(row.is_group) or cint(row.disabled):
		frappe.throw(_("Expense Account must be an active leaf Expense account."))


def _validate_payment_account(account: str, company: str) -> None:
	row = frappe.db.get_value(
		"Account",
		account,
		["company", "account_type", "is_group", "disabled"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Paid From account {0} does not exist.").format(account))
	if row.company != company:
		frappe.throw(_("Paid From account belongs to another Company."))
	if row.account_type not in {"Cash", "Bank"}:
		frappe.throw(_("Paid From account must be a Cash or Bank account."))
	if cint(row.is_group) or cint(row.disabled):
		frappe.throw(_("Paid From account must be an active leaf account."))


def _validate_cost_center(cost_center: str, company: str) -> None:
	row = frappe.db.get_value(
		"Cost Center",
		cost_center,
		["company", "is_group", "disabled"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Cost Center {0} does not exist.").format(cost_center))
	if row.company != company:
		frappe.throw(_("Cost Center belongs to another Company."))
	if cint(row.is_group) or cint(getattr(row, "disabled", 0)):
		frappe.throw(_("Cost Center must be an active leaf Cost Center."))


def _validate_project(project: str, company: str) -> None:
	if not frappe.db.exists("DocType", "Project"):
		frappe.throw(_("Project is unavailable on this site."))
	row = frappe.db.get_value("Project", project, ["company", "status"], as_dict=True)
	if not row:
		frappe.throw(_("Project {0} does not exist.").format(project))
	if row.company and row.company != company:
		frappe.throw(_("Project belongs to another Company."))


def _search_companies(*, txt: str, limit: int) -> list[dict[str, Any]]:
	rows = frappe.get_list(
		"Company",
		or_filters={
			"name": ["like", f"%{txt}%"],
			"company_name": ["like", f"%{txt}%"],
		},
		fields=["name", "company_name"],
		order_by="company_name asc, name asc",
		limit_page_length=limit,
	)
	return [
		{"value": row.name, "label": row.company_name or row.name}
		for row in rows
	]


def _search_branches(
	*,
	txt: str,
	company: str,
	limit: int,
) -> list[dict[str, Any]]:
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	if scope.get("restricted"):
		branches = [
			str(value)
			for value in scope.get("allowed_branches") or []
			if str(value or "").strip()
		]
	else:
		profiles = get_enabled_branch_profiles(company=company)
		branches = [str(row.get("branch") or "") for row in profiles]
		if not branches:
			branches = frappe.get_all("Branch", pluck="name", limit_page_length=0)
	needle = txt.lower()
	return [
		{"value": value, "label": value}
		for value in sorted(dict.fromkeys(branches))
		if value and (not needle or needle in value.lower())
	][:limit]


def _search_categories(
	*,
	txt: str,
	company: str,
	limit: int,
) -> list[dict[str, Any]]:
	filters = [[CATEGORY_DOCTYPE, "is_active", "=", 1]]
	if txt:
		filters.append([CATEGORY_DOCTYPE, "category_name", "like", f"%{txt}%"])
	rows = frappe.get_list(
		CATEGORY_DOCTYPE,
		filters=filters,
		or_filters=[
			[CATEGORY_DOCTYPE, "company", "=", company],
			[CATEGORY_DOCTYPE, "company", "is", "not set"],
		],
		fields=["name", "category_name", "description"],
		order_by="category_name asc",
		limit_page_length=limit,
	)
	return [
		{
			"value": row.name,
			"label": row.category_name or row.name,
			"description": row.description or "",
		}
		for row in rows
	]


def _search_payment_accounts(
	*,
	txt: str,
	company: str,
	limit: int,
) -> list[dict[str, Any]]:
	rows = frappe.get_list(
		"Account",
		filters={
			"company": company,
			"is_group": 0,
			"disabled": 0,
			"account_type": ["in", ["Cash", "Bank"]],
		},
		or_filters={
			"name": ["like", f"%{txt}%"],
			"account_name": ["like", f"%{txt}%"],
		},
		fields=["name", "account_name", "account_type"],
		order_by="account_name asc, name asc",
		limit_page_length=limit,
	)
	return [
		{
			"value": row.name,
			"label": row.account_name or row.name,
			"description": row.account_type or "",
		}
		for row in rows
	]


def _search_cost_centers(
	*,
	txt: str,
	company: str,
	limit: int,
) -> list[dict[str, Any]]:
	filters = {"company": company, "is_group": 0}
	meta = frappe.get_meta("Cost Center")
	if meta.has_field("disabled"):
		filters["disabled"] = 0
	rows = frappe.get_list(
		"Cost Center",
		filters=filters,
		or_filters={
			"name": ["like", f"%{txt}%"],
			"cost_center_name": ["like", f"%{txt}%"],
		},
		fields=["name", "cost_center_name"],
		order_by="cost_center_name asc, name asc",
		limit_page_length=limit,
	)
	return [
		{"value": row.name, "label": row.cost_center_name or row.name}
		for row in rows
	]


def _search_projects(
	*,
	txt: str,
	company: str,
	limit: int,
) -> list[dict[str, Any]]:
	if not frappe.db.exists("DocType", "Project"):
		return []
	rows = frappe.get_list(
		"Project",
		filters={"company": company},
		or_filters={
			"name": ["like", f"%{txt}%"],
			"project_name": ["like", f"%{txt}%"],
		},
		fields=["name", "project_name", "status"],
		order_by="modified desc",
		limit_page_length=limit,
	)
	return [
		{
			"value": row.name,
			"label": row.project_name or row.name,
			"description": row.status or "",
		}
		for row in rows
	]


def _search_suppliers(*, txt: str, limit: int) -> list[dict[str, Any]]:
	rows = frappe.get_list(
		"Supplier",
		filters={"disabled": 0},
		or_filters={
			"name": ["like", f"%{txt}%"],
			"supplier_name": ["like", f"%{txt}%"],
		},
		fields=["name", "supplier_name"],
		order_by="supplier_name asc, name asc",
		limit_page_length=limit,
	)
	return [
		{"value": row.name, "label": row.supplier_name or row.name}
		for row in rows
	]


def _get_business_expense_for_action(name: str):
	doc = frappe.get_doc(BUSINESS_EXPENSE_DOCTYPE, name)
	if not frappe.has_permission(BUSINESS_EXPENSE_DOCTYPE, "read", doc=doc):
		frappe.throw(
			_("You do not have permission to view this Business Expense."),
			frappe.PermissionError,
		)
	return doc


def _get_business_expense_for_review(name: str):
	doc = _get_business_expense_for_action(name)
	if not user_is_business_expense_reviewer():
		frappe.throw(
			_("You do not have Business Expense reviewer access."),
			frappe.PermissionError,
		)
	return doc


def _assert_not_self_approval(doc) -> None:
	if (
		frappe.session.user == getattr(doc, "requested_by", None)
		and "System Manager" not in set(frappe.get_roles(frappe.session.user))
	):
		frappe.throw(_("You cannot approve your own Business Expense."))


def _assert_feature_enabled() -> None:
	if not get_business_expense_settings()["enabled"]:
		frappe.throw(_("Business Expenses are disabled in RetailEdge Settings."))


def _assert_company_access(company: str) -> None:
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(
			_("You do not have permission to use Company {0}.").format(company),
			frappe.PermissionError,
		)


def _business_expense_payload(
	doc,
	*,
	include_workflow: bool,
) -> dict[str, Any]:
	result = {
		"doctype": doc.doctype,
		"name": doc.name,
		"modified": str(getattr(doc, "modified", "") or ""),
		"docstatus": int(getattr(doc, "docstatus", 0) or 0),
		"company": getattr(doc, "company", None) or "",
		"branch": getattr(doc, "branch", None) or "",
		"expense_date": getattr(doc, "expense_date", None),
		"expense_category": getattr(doc, "expense_category", None) or "",
		"amount": flt(getattr(doc, "amount", 0)),
		"description": getattr(doc, "description", None) or "",
		"payee_type": getattr(doc, "payee_type", None) or "Other",
		"supplier": getattr(doc, "supplier", None) or "",
		"payee_name": getattr(doc, "payee_name", None) or "",
		"reference_no": getattr(doc, "reference_no", None) or "",
		"attachment": getattr(doc, "attachment", None) or "",
		"expense_account": getattr(doc, "expense_account", None) or "",
		"payment_account": getattr(doc, "payment_account", None) or "",
		"cost_center": getattr(doc, "cost_center", None) or "",
		"project": getattr(doc, "project", None) or "",
		"expense_status": getattr(doc, "expense_status", None) or "Draft",
		"ledger_status": getattr(doc, "ledger_status", None) or "Not Applicable",
		"workflow_state": getattr(doc, "workflow_state", None) or "",
		"requested_by": getattr(doc, "requested_by", None) or "",
		"approved_by": getattr(doc, "approved_by", None) or "",
		"approved_on": getattr(doc, "approved_on", None),
		"rejected_by": getattr(doc, "rejected_by", None) or "",
		"rejected_on": getattr(doc, "rejected_on", None),
		"review_remarks": getattr(doc, "review_remarks", None) or "",
		"posting_reference_type": getattr(doc, "posting_reference_type", None) or "",
		"posting_reference": getattr(doc, "posting_reference", None) or "",
		"posting_ready": cint(getattr(doc, "posting_ready", 0)),
		"posting_block_reason": getattr(doc, "posting_block_reason", None) or "",
		"reversal_reference_type": getattr(doc, "reversal_reference_type", None) or "",
		"reversal_reference": getattr(doc, "reversal_reference", None) or "",
		"reversal_posting_date": getattr(doc, "reversal_posting_date", None),
		"reversal_reason": getattr(doc, "reversal_reason", None) or "",
		"reversed_by": getattr(doc, "reversed_by", None) or "",
		"reversed_on": getattr(doc, "reversed_on", None),
		"can_edit": bool(
			int(getattr(doc, "docstatus", 0) or 0) == 0
			and doc.has_permission("write")
		),
		"settings": get_business_expense_settings(),
	}
	if include_workflow:
		from retailedge.workflow_readiness import get_workflow_readiness

		result["workflow_readiness"] = get_workflow_readiness(
			doctype=doc.doctype,
			doc=doc,
		)
	return result


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Restrict direct Business Expense reads to readable Company and Branch scope."""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	if not set(frappe.get_roles(user)).intersection(BUSINESS_EXPENSE_READ_ROLES):
		return "1=0"

	clauses: list[str] = []
	for company in _readable_companies(user):
		scope = get_operational_branch_scope(company, user=user)
		company_sql = (
			f"`tab{BUSINESS_EXPENSE_DOCTYPE}`.`company` = "
			f"{frappe.db.escape(company)}"
		)
		if not scope.get("restricted"):
			clauses.append(f"({company_sql})")
			continue
		allowed = [
			str(value).strip()
			for value in dict.fromkeys(scope.get("allowed_branches") or [])
			if str(value or "").strip()
		]
		for branch in allowed:
			branch_sql = (
				f"`tab{BUSINESS_EXPENSE_DOCTYPE}`.`branch` = "
				f"{frappe.db.escape(branch)}"
			)
			clauses.append(f"({company_sql} AND {branch_sql})")
	return f"({' OR '.join(clauses)})" if clauses else "1=0"


def has_permission(
	doc,
	user: str | None = None,
	permission_type: str | None = None,
) -> bool:
	"""Apply Company/Branch scope to direct record access in addition to role permissions."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	if not set(frappe.get_roles(user)).intersection(BUSINESS_EXPENSE_READ_ROLES):
		return False
	company = str(getattr(doc, "company", None) or "").strip()
	branch = str(getattr(doc, "branch", None) or "").strip()
	if not company or not frappe.has_permission("Company", "read", doc=company, user=user):
		return False
	try:
		scope = get_operational_branch_scope(company, user=user)
	except (frappe.PermissionError, frappe.ValidationError):
		return False
	if not scope.get("restricted"):
		return True
	allowed = {
		str(value).strip()
		for value in scope.get("allowed_branches") or []
		if str(value or "").strip()
	}
	return bool(branch and branch in allowed)


def _readable_companies(user: str) -> list[str]:
	companies = frappe.get_all("Company", pluck="name", limit_page_length=0)
	return [
		company
		for company in companies
		if frappe.has_permission("Company", "read", doc=company, user=user)
	]


def _coerce_values(values: dict[str, Any] | str | None) -> dict[str, Any]:
	if not values:
		return {}
	parsed = frappe.parse_json(values) if isinstance(values, str) else values
	if isinstance(parsed, frappe._dict):
		return dict(parsed)
	if isinstance(parsed, dict):
		return dict(parsed)
	frappe.throw(_("Invalid Business Expense values."))
	return {}
