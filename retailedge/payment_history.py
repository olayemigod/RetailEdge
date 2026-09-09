from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.advanced_payments import PAYMENT_ENTRY_DOCTYPE, _payment_branch_field
from retailedge.operating_context import get_operational_branch_scope, validate_operating_branch
from retailedge.standard_customer_payment_submit import get_customer_payment_submit_preview
from retailedge.standard_supplier_payment_submit import get_supplier_payment_submit_preview

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
NO_BRANCH_SCOPE_SENTINEL = "__never__"
ALLOWED_PARTY_TYPES = {"Customer", "Supplier"}
ALLOWED_PAYMENT_TYPES = {"Receive", "Pay", "Internal Transfer"}
DOCSTATUS_FILTERS = {
	"draft": 0,
	"submitted": 1,
	"cancelled": 2,
}


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _assert_read_permission(doctype: str, name: str) -> None:
	doc = frappe.get_doc(doctype, name)
	if not frappe.has_permission(doctype, "read", doc=doc):
		frappe.throw(_("You do not have read permission for {0} {1}.").format(_(doctype), name), frappe.PermissionError)


def _resolve_branch_condition(company: str, branch: str = "") -> tuple[str | None, Any, dict[str, Any]]:
	branch_field = _payment_branch_field()
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	allowed = list(scope.get("allowed_branches") or [])
	branch = _clean(branch)

	if branch:
		validate_operating_branch(company=company, branch=branch, user=frappe.session.user, throw=True)
		if scope.get("restricted") and branch not in allowed:
			frappe.throw(_("You do not have active operational access to Branch {0}.").format(branch), frappe.PermissionError)
		if not branch_field:
			frappe.throw(_("Payment Entry branch attribution is unavailable. Run the site migration before using Branch-scoped payment history."))
		return branch_field, branch, scope

	if not scope.get("restricted"):
		return branch_field, None, scope
	if not branch_field:
		return branch_field, NO_BRANCH_SCOPE_SENTINEL, scope
	if not allowed:
		return branch_field, NO_BRANCH_SCOPE_SENTINEL, scope
	if len(allowed) == 1:
		return branch_field, allowed[0], scope
	return branch_field, ["in", allowed], scope


def _normalise_docstatus(value: str) -> int | None:
	value = _clean(value).lower()
	if not value or value == "all":
		return None
	if value not in DOCSTATUS_FILTERS:
		frappe.throw(_("Unsupported payment document state."))
	return DOCSTATUS_FILTERS[value]


def _validate_party_filters(party_type: str, party: str) -> tuple[str, str]:
	party_type = _clean(party_type)
	party = _clean(party)
	if party_type and party_type not in ALLOWED_PARTY_TYPES:
		frappe.throw(_("Payment History supports Customer or Supplier party filtering."))
	if party and not party_type:
		frappe.throw(_("Choose Party Type before filtering by Party."))
	if party:
		_assert_read_permission(party_type, party)
	return party_type, party


def _validate_payment_type(value: str) -> str:
	value = _clean(value)
	if value and value not in ALLOWED_PAYMENT_TYPES:
		frappe.throw(_("Unsupported Payment Type filter."))
	return value


def _page_size(value: int | str) -> int:
	return max(1, min(cint(value) or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE))


def _row_branch(row: Any, branch_field: str | None) -> str:
	return _clean(row.get(branch_field)) if branch_field else ""


@frappe.whitelist()
def list_payment_history(
	company: str,
	branch: str = "",
	party_type: str = "",
	party: str = "",
	payment_type: str = "",
	docstatus: str = "all",
	from_date: str = "",
	to_date: str = "",
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	"""Return a bounded permission-visible ERPNext Payment Entry history page."""
	company = _clean(company)
	if not company:
		frappe.throw(_("Company is required."))
	_assert_read_permission("Company", company)
	party_type, party = _validate_party_filters(party_type, party)
	payment_type = _validate_payment_type(payment_type)
	resolved_docstatus = _normalise_docstatus(docstatus)
	branch_field, branch_condition, scope = _resolve_branch_condition(company, branch)

	filters: dict[str, Any] = {"company": company}
	if branch_field and branch_condition is not None:
		filters[branch_field] = branch_condition
	elif branch_condition == NO_BRANCH_SCOPE_SENTINEL:
		filters["name"] = NO_BRANCH_SCOPE_SENTINEL
	if party_type:
		filters["party_type"] = party_type
	if party:
		filters["party"] = party
	if payment_type:
		filters["payment_type"] = payment_type
	if resolved_docstatus is not None:
		filters["docstatus"] = resolved_docstatus
	if _clean(from_date) and _clean(to_date):
		filters["posting_date"] = ["between", [_clean(from_date), _clean(to_date)]]
	elif _clean(from_date):
		filters["posting_date"] = [">=", _clean(from_date)]
	elif _clean(to_date):
		filters["posting_date"] = ["<=", _clean(to_date)]

	page_size = _page_size(page_size)
	page = max(1, cint(page) or 1)
	start = (page - 1) * page_size
	fields = [
		"name",
		"posting_date",
		"payment_type",
		"party_type",
		"party",
		"mode_of_payment",
		"paid_amount",
		"received_amount",
		"unallocated_amount",
		"status",
		"docstatus",
		"modified",
	]
	if branch_field:
		fields.append(branch_field)

	rows = frappe.get_list(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		fields=fields,
		order_by="posting_date desc, modified desc, name desc",
		start=start,
		page_length=page_size + 1,
	)
	has_next = len(rows) > page_size
	rows = rows[:page_size]
	return {
		"rows": [
			{
				"payment_entry": row.name,
				"posting_date": row.posting_date,
				"payment_type": row.payment_type or "",
				"party_type": row.party_type or "",
				"party": row.party or "",
				"branch": _row_branch(row, branch_field),
				"mode_of_payment": row.mode_of_payment or "",
				"paid_amount": flt(row.paid_amount),
				"received_amount": flt(row.received_amount),
				"unallocated_amount": flt(row.unallocated_amount),
				"status": row.status or ("Draft" if cint(row.docstatus) == 0 else "Cancelled" if cint(row.docstatus) == 2 else "Submitted"),
				"docstatus": cint(row.docstatus),
				"modified": str(row.modified or ""),
			}
			for row in rows
		],
		"pagination": {
			"page": page,
			"page_size": page_size,
			"has_previous": page > 1,
			"has_next": has_next,
		},
		"scope": {
			"restricted": bool(scope.get("restricted")),
			"source": scope.get("source") or "",
			"allowed_branches": list(scope.get("allowed_branches") or []),
		},
		"source_of_truth": "ERPNext Payment Entry",
	}


def _assert_detail_scope(doc: Any, company: str = "", branch: str = "") -> str:
	company = _clean(company) or _clean(getattr(doc, "company", ""))
	if _clean(getattr(doc, "company", "")) != company:
		frappe.throw(_("Payment Entry does not belong to the selected Company."), frappe.PermissionError)
	branch_field, _condition, scope = _resolve_branch_condition(company, branch)
	payment_branch = _clean(getattr(doc, branch_field, "")) if branch_field else ""
	allowed = list(scope.get("allowed_branches") or [])
	if _clean(branch) and payment_branch != _clean(branch):
		frappe.throw(_("Payment Entry does not belong to the selected Branch."), frappe.PermissionError)
	if scope.get("restricted"):
		if not allowed or not payment_branch or payment_branch not in allowed:
			frappe.throw(_("Payment Entry is outside your active operational Branch access."), frappe.PermissionError)
	return payment_branch


def _standard_draft_review(doc: Any, payment_branch: str) -> dict[str, Any]:
	if cint(getattr(doc, "docstatus", 0)) != 0:
		return {"kind": "read_only", "advanced_only": False, "review": None, "blockers": []}
	company = _clean(getattr(doc, "company", ""))
	party_type = _clean(getattr(doc, "party_type", ""))
	party = _clean(getattr(doc, "party", ""))
	payment_type = _clean(getattr(doc, "payment_type", ""))
	try:
		if payment_type == "Receive" and party_type == "Customer":
			review = get_customer_payment_submit_preview(
				payment_entry=doc.name,
				company=company,
				customer=party,
				branch=payment_branch or None,
			)
			return {
				"kind": "standard_customer",
				"advanced_only": not bool(review.get("can_submit")),
				"review": review,
				"blockers": list(review.get("blockers") or []),
			}
		if payment_type == "Pay" and party_type == "Supplier":
			review = get_supplier_payment_submit_preview(
				payment_entry=doc.name,
				company=company,
				supplier=party,
				branch=payment_branch or None,
			)
			return {
				"kind": "standard_supplier",
				"advanced_only": not bool(review.get("can_submit")),
				"review": review,
				"blockers": list(review.get("blockers") or []),
			}
	except frappe.PermissionError:
		raise
	except Exception:
		return {
			"kind": "advanced",
			"advanced_only": True,
			"review": None,
			"blockers": [_("This draft requires Advanced ERPNext review.")],
		}
	return {
		"kind": "advanced",
		"advanced_only": True,
		"review": None,
		"blockers": [_("This Payment Entry shape is outside standard RetailEdge submission." )],
	}


@frappe.whitelist()
def get_payment_history_detail(
	payment_entry: str,
	company: str = "",
	branch: str = "",
) -> dict[str, Any]:
	"""Return a read-only, branch-safe Payment Entry detail with standard-draft classification."""
	payment_entry = _clean(payment_entry)
	if not payment_entry or not frappe.db.exists(PAYMENT_ENTRY_DOCTYPE, payment_entry):
		frappe.throw(_("Payment Entry {0} does not exist.").format(payment_entry or "(blank)"))
	doc = frappe.get_doc(PAYMENT_ENTRY_DOCTYPE, payment_entry)
	if not frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "read", doc=doc):
		frappe.throw(_("You do not have read permission for Payment Entry {0}.").format(payment_entry), frappe.PermissionError)
	payment_branch = _assert_detail_scope(doc, company=company, branch=branch)
	classification = _standard_draft_review(doc, payment_branch)
	references = [
		{
			"reference_doctype": _clean(getattr(row, "reference_doctype", "")),
			"reference_name": _clean(getattr(row, "reference_name", "")),
			"allocated_amount": flt(getattr(row, "allocated_amount", 0)),
			"outstanding_amount": flt(getattr(row, "outstanding_amount", 0)),
		}
		for row in list(getattr(doc, "references", None) or [])
	]
	return {
		"payment_entry": doc.name,
		"company": _clean(getattr(doc, "company", "")),
		"branch": payment_branch,
		"posting_date": str(getattr(doc, "posting_date", "") or ""),
		"payment_type": _clean(getattr(doc, "payment_type", "")),
		"party_type": _clean(getattr(doc, "party_type", "")),
		"party": _clean(getattr(doc, "party", "")),
		"mode_of_payment": _clean(getattr(doc, "mode_of_payment", "")),
		"paid_from": _clean(getattr(doc, "paid_from", "")),
		"paid_to": _clean(getattr(doc, "paid_to", "")),
		"paid_amount": flt(getattr(doc, "paid_amount", 0)),
		"received_amount": flt(getattr(doc, "received_amount", 0)),
		"unallocated_amount": flt(getattr(doc, "unallocated_amount", 0)),
		"reference_no": _clean(getattr(doc, "reference_no", "")),
		"reference_date": str(getattr(doc, "reference_date", "") or ""),
		"remarks": _clean(getattr(doc, "remarks", "")),
		"status": _clean(getattr(doc, "status", "")),
		"docstatus": cint(getattr(doc, "docstatus", 0)),
		"modified": str(getattr(doc, "modified", "") or ""),
		"references": references,
		"standard_review": classification,
		"source_of_truth": "ERPNext Payment Entry",
	}
