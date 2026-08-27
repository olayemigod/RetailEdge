from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

from retailedge.branch_profile import get_exact_branch_profile


ROLE_TYPES = {"Cashier", "Manager", "Auditor", "Sales", "Stock", "Accounts", "Purchasing", "Other"}
IMMUTABLE_ASSIGNMENT_FIELDS = (
	"user",
	"company",
	"branch",
	"branch_setup",
	"branch_role",
	"is_primary",
	"effective_from",
	"effective_to",
)
ASSIGNMENT_LIST_FIELDS = (
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
)


def get_active_branch_assignments(
	user: str | None = None,
	company: str | None = None,
	as_of=None,
) -> list[dict[str, Any]]:
	"""Return effective assignments using date predicates in the database.

	Saved ``status`` is deliberately not an access authority. Effective dates are
	the truth so time passing can activate/end access without an edit or scheduler.
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
	}
	if company:
		filters["company"] = company
	rows = frappe.get_list(
		"RetailEdge Branch Assignment",
		filters=filters,
		or_filters=[
			["RetailEdge Branch Assignment", "effective_to", "is", "not set"],
			["RetailEdge Branch Assignment", "effective_to", ">=", as_of],
		],
		fields=list(ASSIGNMENT_LIST_FIELDS),
		order_by="is_primary desc, effective_from desc, branch asc",
		limit_page_length=200,
	)
	return [dict(row) for row in rows]


def get_assignment_branches(user: str | None = None, company: str | None = None, as_of=None) -> list[str]:
	return list(
		dict.fromkeys(
			row.get("branch")
			for row in get_active_branch_assignments(user=user, company=company, as_of=as_of)
			if row.get("branch")
		)
	)


def get_primary_assignment_branch(user: str | None = None, company: str | None = None, as_of=None) -> str | None:
	rows = get_active_branch_assignments(user=user, company=company, as_of=as_of)
	primary = [row.get("branch") for row in rows if row.get("is_primary") and row.get("branch")]
	if len(primary) == 1:
		return primary[0]
	if len(rows) == 1:
		return rows[0].get("branch")
	return None


def has_branch_assignments(user: str | None = None) -> bool:
	"""Return whether assignment history exists, not merely whether one is active."""
	if not _has_assignment_doctype():
		return False
	user = user or getattr(frappe.session, "user", None)
	if not user:
		return False
	return bool(frappe.db.exists("RetailEdge Branch Assignment", {"user": user}))


@frappe.whitelist()
def get_branch_assignment_context(filters=None, limit: int = 200) -> dict[str, Any]:
	"""Return bounded, permission-scoped assignment history for EdgeSuite."""
	_assert_assignment_read()
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	query_filters: dict[str, Any] = {}
	for fieldname in ("user", "company", "branch"):
		value = str(filters.get(fieldname) or "").strip()
		if value:
			query_filters[fieldname] = value
	query_filters = _scope_assignment_filters(query_filters)
	requested_status = str(filters.get("status") or "").strip()
	limit = min(max(int(limit or 200), 1), 500)
	or_filters = _apply_status_filters(query_filters, requested_status)
	rows = frappe.get_list(
		"RetailEdge Branch Assignment",
		filters=query_filters,
		or_filters=or_filters,
		fields=list(ASSIGNMENT_LIST_FIELDS),
		order_by="effective_from desc, modified desc",
		limit_page_length=limit,
	)
	assignments = []
	for row in rows:
		item = dict(row)
		item["status"] = _status_for_dates(
			getdate(item.get("effective_from")),
			getdate(item.get("effective_to")) if item.get("effective_to") else None,
		)
		assignments.append(item)
	return {
		"assignments": assignments,
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

	_lock_assignment_user(old.user)
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
	old.flags.controlled_assignment_update = True
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
	_validate_assignment_user(doc.user)
	if not doc.company:
		frappe.throw(_("Company is required."))
	if not doc.branch:
		frappe.throw(_("Branch is required."))
	if not doc.effective_from:
		frappe.throw(_("Effective From is required."))
	if doc.branch_role not in ROLE_TYPES:
		frappe.throw(_("Choose a valid Branch Role."))

	_validate_assignment_immutability(doc)
	_lock_assignment_user(doc.user)
	start = getdate(doc.effective_from)
	end = getdate(doc.effective_to) if doc.effective_to else None
	if end and end < start:
		frappe.throw(_("Effective To cannot be before Effective From."))

	if not getattr(doc.flags, "controlled_branch_setup_relink", False):
		profile = _validate_company_branch(doc.company, doc.branch)
		doc.branch_setup = profile.name
	doc.status = _status_for_dates(start, end)
	_validate_same_branch_overlap(doc, start, end)
	if int(doc.is_primary or 0):
		_validate_primary_overlap(doc, start, end)


def get_branch_setup_assignment_blockers(branch_setup: str, as_of=None) -> list[dict[str, Any]]:
	"""Current/future assignments that must be ended/transferred before setup changes."""
	if not branch_setup or not _has_assignment_doctype():
		return []
	as_of = getdate(as_of or nowdate())
	rows = frappe.db.sql(
		"""
		select name, user, company, branch, effective_from, effective_to
		from `tabRetailEdge Branch Assignment`
		where branch_setup = %(branch_setup)s
		  and (effective_to is null or effective_to >= %(as_of)s)
		order by effective_from asc, user asc
		limit 20
		""",
		{"branch_setup": branch_setup, "as_of": as_of},
		as_dict=True,
	)
	return [dict(row) for row in rows]


def has_branch_setup_assignment_history(branch_setup: str) -> bool:
	if not branch_setup or not _has_assignment_doctype():
		return False
	return bool(frappe.db.exists("RetailEdge Branch Assignment", {"branch_setup": branch_setup}))


def relink_ended_assignments_to_history(old_setup: str, historical_setup: str, as_of=None) -> int:
	"""Move only ended assignment links to the archived Branch Setup record."""
	if not old_setup or not historical_setup or not _has_assignment_doctype():
		return 0
	as_of = getdate(as_of or nowdate())
	names = frappe.get_all(
		"RetailEdge Branch Assignment",
		filters={"branch_setup": old_setup, "effective_to": ["<", as_of]},
		pluck="name",
		limit_page_length=0,
	)
	count = 0
	for name in names:
		doc = frappe.get_doc("RetailEdge Branch Assignment", name)
		doc.branch_setup = historical_setup
		doc.flags.controlled_branch_setup_relink = True
		doc.save()
		count += 1
	return count


def _validate_assignment_user(user: str) -> None:
	user = str(user or "").strip()
	if not user:
		frappe.throw(_("User is required."))
	if not frappe.db.exists("User", user):
		frappe.throw(_("User {0} does not exist.").format(user))
	if not frappe.has_permission("User", "read", doc=user):
		frappe.throw(_("You do not have permission to assign User {0}.").format(user), frappe.PermissionError)
	enabled, user_type = frappe.db.get_value("User", user, ["enabled", "user_type"]) or (0, "")
	if not int(enabled or 0) or user_type != "System User":
		frappe.throw(_("Branch Assignments require an enabled System User."))


def _validate_company_branch(company: str, branch: str):
	_assert_master_read("Company", company)
	_assert_master_read("Branch", branch)
	profile = get_exact_branch_profile(company=company, branch=branch, active_only=True)
	if not profile:
		frappe.throw(_("Branch {0} is not enabled in Branch Setup for Company {1}.").format(branch, company))
	if not profile.has_permission("read"):
		frappe.throw(_("You do not have permission to use this Branch Setup."), frappe.PermissionError)
	return profile


def _validate_assignment_immutability(doc) -> None:
	if doc.is_new() or not doc.name:
		return
	if getattr(doc.flags, "controlled_assignment_update", False):
		return
	stored = frappe.db.get_value(
		"RetailEdge Branch Assignment",
		doc.name,
		list(IMMUTABLE_ASSIGNMENT_FIELDS),
		as_dict=True,
	)
	if not stored:
		return
	allowed_relink = getattr(doc.flags, "controlled_branch_setup_relink", False)
	changed = []
	for fieldname in IMMUTABLE_ASSIGNMENT_FIELDS:
		if allowed_relink and fieldname == "branch_setup":
			continue
		old_value = _comparison_value(fieldname, stored.get(fieldname))
		new_value = _comparison_value(fieldname, getattr(doc, fieldname, None))
		if old_value != new_value:
			changed.append(fieldname)
	if changed:
		frappe.throw(
			_(
				"Saved Branch Assignment history cannot be rewritten directly ({0}). "
				"Use Transfer for posting changes; only notes/reasons may be edited on an existing record."
			).format(", ".join(changed))
		)


def _comparison_value(fieldname: str, value):
	if fieldname in {"effective_from", "effective_to"}:
		return getdate(value) if value else None
	if fieldname == "is_primary":
		return int(value or 0)
	return str(value or "").strip()


def _lock_assignment_user(user: str) -> None:
	if not user:
		return
	frappe.db.sql("select name from `tabUser` where name = %s for update", (user,))


def _validate_same_branch_overlap(doc, start, end) -> None:
	conflict = _find_overlap(
		user=doc.user,
		company=doc.company,
		branch=doc.branch,
		start=start,
		end=end,
		exclude_name=doc.name,
	)
	if conflict:
		frappe.throw(
			_("This user already has an overlapping assignment to Branch {0}: {1}.").format(
				doc.branch,
				conflict,
			)
		)


def _validate_primary_overlap(doc, start, end) -> None:
	conflict = _find_overlap(
		user=doc.user,
		company=doc.company,
		branch=None,
		start=start,
		end=end,
		exclude_name=doc.name,
		primary_only=True,
	)
	if conflict:
		frappe.throw(
			_("A user can have only one Primary Branch assignment for the same Company at a time: {0}.").format(
				conflict
			)
		)


def _find_overlap(
	*,
	user: str,
	company: str,
	branch: str | None,
	start,
	end,
	exclude_name: str | None,
	primary_only: bool = False,
) -> str | None:
	conditions = [
		"user = %(user)s",
		"company = %(company)s",
		"name != %(exclude_name)s",
		"effective_from <= %(end_bound)s",
		"(effective_to is null or effective_to >= %(start)s)",
	]
	values = {
		"user": user,
		"company": company,
		"exclude_name": exclude_name or "",
		"start": getdate(start),
		"end_bound": getdate(end) if end else date(9999, 12, 31),
	}
	if branch:
		conditions.append("branch = %(branch)s")
		values["branch"] = branch
	if primary_only:
		conditions.append("is_primary = 1")
	rows = frappe.db.sql(
		f"""
		select name
		from `tabRetailEdge Branch Assignment`
		where {' and '.join(conditions)}
		order by effective_from asc
		limit 1
		""",
		values,
		pluck=True,
	)
	return str(rows[0]) if rows else None


def _ranges_overlap(start_a, end_a, start_b, end_b) -> bool:
	return (end_b is None or start_a <= end_b) and (end_a is None or start_b <= end_a)


def _status_for_dates(start, end) -> str:
	today = getdate(nowdate())
	if start > today:
		return "Planned"
	if end and end < today:
		return "Ended"
	return "Active"


def _apply_status_filters(query_filters: dict[str, Any], requested_status: str):
	today = getdate(nowdate())
	if not requested_status:
		return None
	if requested_status == "Planned":
		query_filters["effective_from"] = [">", today]
		return None
	if requested_status == "Ended":
		query_filters["effective_to"] = ["<", today]
		return None
	if requested_status == "Active":
		query_filters["effective_from"] = ["<=", today]
		return [
			["RetailEdge Branch Assignment", "effective_to", "is", "not set"],
			["RetailEdge Branch Assignment", "effective_to", ">=", today],
		]
	frappe.throw(_("Choose a valid Branch Assignment status."))


def _scope_assignment_filters(query_filters: dict[str, Any]) -> dict[str, Any]:
	from retailedge.branch_context import get_user_allowed_branches, user_has_global_branch_access

	user = frappe.session.user
	if user_has_global_branch_access(user=user):
		return query_filters
	allowed = get_user_allowed_branches(user=user, company=query_filters.get("company") or None)
	branches = [str(value or "").strip() for value in allowed.get("branches") or [] if str(value or "").strip()]
	requested_branch = str(query_filters.get("branch") or "").strip()
	if requested_branch and requested_branch not in branches:
		query_filters["name"] = "__no_visible_branch_assignment__"
		return query_filters
	if branches:
		query_filters["branch"] = ["in", branches]
	else:
		query_filters["name"] = "__no_visible_branch_assignment__"
	return query_filters


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
		"status": _status_for_dates(
			getdate(doc.effective_from),
			getdate(doc.effective_to) if doc.effective_to else None,
		),
		"is_primary": int(doc.is_primary or 0),
	}


def _assert_master_read(doctype: str, name: str) -> None:
	name = str(name or "").strip()
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to use {0} {1}.").format(doctype, name), frappe.PermissionError)


def _assert_assignment_read() -> None:
	if not frappe.has_permission("RetailEdge Branch Assignment", "read"):
		frappe.throw(_("You do not have permission to view Branch Assignments."), frappe.PermissionError)


def _has_assignment_doctype() -> bool:
	try:
		return bool(frappe.db.exists("DocType", "RetailEdge Branch Assignment"))
	except Exception:
		return False
