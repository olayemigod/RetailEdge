from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

from retailedge.branch_profile import get_exact_branch_profile


ACTIVE_STATUSES = {"Active", "Planned", "Ended"}
ROLE_TYPES = {"Cashier", "Manager", "Auditor", "Sales", "Stock", "Accounts", "Purchasing", "Other"}


def get_active_branch_assignments(user: str | None = None, company: str | None = None, as_of=None) -> list[dict[str, Any]]:
	"""Return effective RetailEdge Branch Assignments for one user.

	The assignment layer is RetailEdge access/history truth. ERPNext permissions
	still apply separately and are never widened by this helper.
	"""
	if not _has_assignment_doctype():
		return []
	user = user or getattr(frappe.session, "user", None)
	if not user:
		return []
	as_of = getdate(as_of or nowdate())
	filters: dict[str, Any] = {
		"user": user,
		"effective_from": ["<=", as_of],
		"status": "Active",
	}
	if company:
		filters["company"] = company
	rows = frappe.get_list(
		"RetailEdge Branch Assignment",
		filters=filters,
		fields=[
			"name",
			"user",
			"company",
			"branch",
			"branch_setup",
			"branch_role",
			"effective_from",
			"effective_to",
			"is_primary",
		],
		order_by="is_primary desc, effective_from desc, branch asc",
		limit_page_length=200,
	)
	return [dict(row) for row in rows if not row.get("effective_to") or getdate(row.get("effective_to")) >= as_of]


def get_assignment_branches(user: str | None = None, company: str | None = None, as_of=None) -> list[str]:
	return list(
		dict.fromkeys(
			row.get("branch")
			for row in get_active_branch_assignments(user=user, company=company, as_of=as_of)
			if row.get("branch")
		)
	)


def has_branch_assignments(user: str | None = None) -> bool:
	if not _has_assignment_doctype():
		return False
	user = user or getattr(frappe.session, "user", None)
	if not user:
		return False
	return bool(frappe.db.exists("RetailEdge Branch Assignment", {"user": user}))


@frappe.whitelist()
def get_branch_assignment_context(filters=None, limit: int = 200) -> dict[str, Any]:
	"""Return bounded assignment history for the dedicated Branch Assignments page."""
	_assert_assignment_read()
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	query_filters: dict[str, Any] = {}
	for fieldname in ("user", "company", "branch", "status"):
		value = str(filters.get(fieldname) or "").strip()
		if value:
			query_filters[fieldname] = value
	limit = min(max(int(limit or 200), 1), 500)
	rows = frappe.get_list(
		"RetailEdge Branch Assignment",
		filters=query_filters,
		fields=[
			"name",
			"user",
			"company",
			"branch",
			"branch_setup",
			"branch_role",
			"effective_from",
			"effective_to",
			"status",
			"is_primary",
			"transfer_reason",
			"modified",
		],
		order_by="effective_from desc, modified desc",
		limit_page_length=limit,
	)
	return {
		"assignments": [dict(row) for row in rows],
		"can_create": bool(frappe.has_permission("RetailEdge Branch Assignment", "create")),
		"can_write": bool(frappe.has_permission("RetailEdge Branch Assignment", "write")),
		"user": frappe.session.user,
		"user_name": frappe.utils.get_fullname(frappe.session.user),
	}


@frappe.whitelist(methods=["POST"])
def create_branch_assignment(
	user: str,
	company: str,
	branch: str,
	effective_from,
	branch_role: str = "Other",
	effective_to=None,
	is_primary: int = 0,
	transfer_reason: str = "",
	notes: str = "",
) -> dict[str, Any]:
	if not frappe.has_permission("RetailEdge Branch Assignment", "create"):
		frappe.throw(_("You do not have permission to create Branch Assignments."), frappe.PermissionError)
	doc = frappe.new_doc("RetailEdge Branch Assignment")
	doc.user = user
	doc.company = company
	doc.branch = branch
	doc.branch_role = branch_role or "Other"
	doc.effective_from = effective_from
	doc.effective_to = effective_to or None
	doc.is_primary = int(is_primary or 0)
	doc.transfer_reason = transfer_reason or ""
	doc.notes = notes or ""
	doc.insert()
	return _assignment_response(doc)


@frappe.whitelist(methods=["POST"])
def transfer_branch_assignment(
	name: str,
	new_company: str,
	new_branch: str,
	effective_date,
	branch_role: str = "",
	reason: str = "",
	notes: str = "",
) -> dict[str, Any]:
	"""Close one assignment and create the next one without rewriting history."""
	old = frappe.get_doc("RetailEdge Branch Assignment", name)
	old.check_permission("write")
	if not frappe.has_permission("RetailEdge Branch Assignment", "create"):
		frappe.throw(_("You do not have permission to create the destination Branch Assignment."), frappe.PermissionError)

	effective_date = getdate(effective_date)
	old_start = getdate(old.effective_from)
	if effective_date <= old_start:
		frappe.throw(_("Transfer date must be after the current assignment start date."))
	if old.effective_to and effective_date > add_days(getdate(old.effective_to), 1):
		frappe.throw(_("Transfer date cannot start after the recorded assignment has already ended."))
	_assert_no_open_pos_work(user=old.user, effective_date=effective_date)
	_validate_company_branch(new_company, new_branch)

	old.effective_to = add_days(effective_date, -1)
	if reason:
		old.transfer_reason = reason
	old.save()

	new_doc = frappe.new_doc("RetailEdge Branch Assignment")
	new_doc.user = old.user
	new_doc.company = new_company
	new_doc.branch = new_branch
	new_doc.branch_role = branch_role or old.branch_role or "Other"
	new_doc.effective_from = effective_date
	new_doc.is_primary = old.is_primary
	new_doc.transfer_reason = reason or _("Transferred from {0}").format(old.branch)
	new_doc.notes = notes or ""
	new_doc.insert()
	return {"previous": _assignment_response(old), "current": _assignment_response(new_doc)}


def validate_branch_assignment(doc) -> None:
	if not doc.user:
		frappe.throw(_("User is required."))
	if not doc.company:
		frappe.throw(_("Company is required."))
	if not doc.branch:
		frappe.throw(_("Branch is required."))
	if not doc.effective_from:
		frappe.throw(_("Effective From is required."))
	if doc.branch_role not in ROLE_TYPES:
		frappe.throw(_("Choose a valid Branch Role."))

	start = getdate(doc.effective_from)
	end = getdate(doc.effective_to) if doc.effective_to else None
	if end and end < start:
		frappe.throw(_("Effective To cannot be before Effective From."))

	profile = _validate_company_branch(doc.company, doc.branch)
	doc.branch_setup = profile.name
	doc.status = _status_for_dates(start, end)
	_validate_same_branch_overlap(doc, start, end)
	if int(doc.is_primary or 0):
		_validate_primary_overlap(doc, start, end)


def _validate_company_branch(company: str, branch: str):
	profile = get_exact_branch_profile(company=company, branch=branch, active_only=True)
	if not profile:
		frappe.throw(_("Branch {0} is not enabled in Branch Setup for Company {1}.").format(branch, company))
	return profile


def _validate_same_branch_overlap(doc, start, end) -> None:
	for row in _user_assignments(doc.user, exclude_name=doc.name):
		if row.get("company") != doc.company or row.get("branch") != doc.branch:
			continue
		if _ranges_overlap(start, end, getdate(row.get("effective_from")), getdate(row.get("effective_to")) if row.get("effective_to") else None):
			frappe.throw(
				_("This user already has an overlapping assignment to Branch {0} for the selected dates.").format(doc.branch)
			)


def _validate_primary_overlap(doc, start, end) -> None:
	for row in _user_assignments(doc.user, exclude_name=doc.name):
		if row.get("company") != doc.company or not int(row.get("is_primary") or 0):
			continue
		if _ranges_overlap(start, end, getdate(row.get("effective_from")), getdate(row.get("effective_to")) if row.get("effective_to") else None):
			frappe.throw(_("A user can have only one Primary Branch assignment for the same Company at a time."))


def _user_assignments(user: str, exclude_name: str | None = None) -> list[dict[str, Any]]:
	filters: dict[str, Any] = {"user": user}
	if exclude_name:
		filters["name"] = ["!=", exclude_name]
	rows = frappe.get_list(
		"RetailEdge Branch Assignment",
		filters=filters,
		fields=["name", "company", "branch", "effective_from", "effective_to", "is_primary"],
		limit_page_length=500,
	)
	return [dict(row) for row in rows]


def _ranges_overlap(start_a, end_a, start_b, end_b) -> bool:
	return (end_b is None or start_a <= end_b) and (end_a is None or start_b <= end_a)


def _status_for_dates(start, end) -> str:
	today = getdate(nowdate())
	if start > today:
		return "Planned"
	if end and end < today:
		return "Ended"
	return "Active"


def _assert_no_open_pos_work(user: str, effective_date) -> None:
	if getdate(effective_date) > getdate(nowdate()):
		return
	try:
		from retailedge.cashier_context import find_open_pos_opening_shift

		opening = find_open_pos_opening_shift(user=user)
	except Exception:
		opening = None
	if opening:
		frappe.throw(_("Close the user's active POS shift before transferring the Branch assignment."))


def _assignment_response(doc) -> dict[str, Any]:
	return {
		"name": doc.name,
		"user": doc.user,
		"company": doc.company,
		"branch": doc.branch,
		"branch_setup": doc.branch_setup,
		"branch_role": doc.branch_role,
		"effective_from": doc.effective_from,
		"effective_to": doc.effective_to,
		"status": doc.status,
		"is_primary": int(doc.is_primary or 0),
	}


def _assert_assignment_read() -> None:
	if not frappe.has_permission("RetailEdge Branch Assignment", "read"):
		frappe.throw(_("You do not have permission to view Branch Assignments."), frappe.PermissionError)


def _has_assignment_doctype() -> bool:
	try:
		return bool(frappe.db.exists("DocType", "RetailEdge Branch Assignment"))
	except Exception:
		return False
