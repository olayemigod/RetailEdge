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

	This is an internal access resolver, so it deliberately does not depend on the
	user having read permission on Branch Assignment history. The query is always
	constrained to the requested user and effective date.
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
	rows = frappe.get_all(
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
	return _attach_assignment_price_lists(rows)


def get_assignment_branches(user: str | None = None, company: str | None = None, as_of=None) -> list[str]:
	return list(
		dict.fromkeys(
			row.get("branch")
			for row in get_active_branch_assignments(user=user, company=company, as_of=as_of)
			if row.get("branch")
		)
	)


def get_raw_assignment_price_lists(
	user: str | None = None,
	company: str | None = None,
	branch: str | None = None,
	mode: str | None = None,
	as_of=None,
) -> list[str]:
	"""Return enabled Price Lists granted by active Branch Assignments without permission recursion."""
	user = user or getattr(frappe.session, "user", None)
	if not user or not frappe.db.exists("DocType", "RetailEdge Branch Assignment Price List"):
		return []
	assignments = get_active_branch_assignments(user=user, company=company, as_of=as_of)
	if branch:
		assignments = [row for row in assignments if row.get("branch") == branch]
	parents = [row.get("name") for row in assignments if row.get("name")]
	if not parents:
		return []
	rows = frappe.get_all(
		"RetailEdge Branch Assignment Price List",
		filters={
			"parent": ["in", parents],
			"parenttype": "RetailEdge Branch Assignment",
			"parentfield": "price_lists",
		},
		fields=["price_list"],
		order_by="idx asc",
		limit_page_length=0,
	)
	result = []
	mode_field = "selling" if mode == "selling" else "buying" if mode == "buying" else ""
	for row in rows:
		name = str(row.get("price_list") or "").strip()
		if not name or name in result:
			continue
		price = frappe.db.get_value("Price List", name, ["enabled", "selling", "buying"], as_dict=True)
		if not price or not int(price.get("enabled") or 0):
			continue
		if mode_field and not int(price.get(mode_field) or 0):
			continue
		result.append(name)
	return result


def get_assignment_price_lists(
	user: str | None = None,
	company: str | None = None,
	branch: str | None = None,
	mode: str | None = None,
	as_of=None,
) -> list[str]:
	"""Return permission-valid Price Lists granted by active effective-dated Branch Assignments."""
	user = user or getattr(frappe.session, "user", None)
	return [
		name
		for name in get_raw_assignment_price_lists(
			user=user,
			company=company,
			branch=branch,
			mode=mode,
			as_of=as_of,
		)
		if frappe.has_permission("Price List", "read", doc=name, user=user)
	]


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
	price_lists_by_assignment = _price_lists_by_assignment([row.get("name") for row in rows if row.get("name")])
	assignments = []
	for row in _attach_assignment_price_lists(rows):
		item = dict(row)
		item["status"] = _status_for_dates(
			getdate(item.get("effective_from")),
			getdate(item.get("effective_to")) if item.get("effective_to") else None,
		)
		item["price_lists"] = price_lists_by_assignment.get(item.get("name"), [])
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
	allowed_price_lists=None,
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
	_set_assignment_price_lists(doc, allowed_price_lists)
	doc.insert()
	return _assignment_response(doc)


@frappe.whitelist(methods=["POST"])
def update_branch_assignment_price_lists(
	name: str,
	price_lists=None,
) -> dict[str, Any]:
	"""Update only current/future Price List access without rewriting posting history."""
	doc = frappe.get_doc("RetailEdge Branch Assignment", name)
	doc.check_permission("write")
	status = _status_for_dates(
		getdate(doc.effective_from),
		getdate(doc.effective_to) if doc.effective_to else None,
	)
	if status == "Ended":
		frappe.throw(
			_("Ended Branch Assignment history cannot be changed. Create a new assignment if access must be restored."),
			frappe.ValidationError,
		)
	_lock_assignment_user(doc.user)
	doc.set("price_lists", [{"price_list": value} for value in _normalise_price_lists(price_lists)])
	doc.flags.controlled_price_list_update = True
	doc.save()
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
	allowed_price_lists=None,
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
	_set_assignment_price_lists(
		new_doc,
		allowed_price_lists if allowed_price_lists is not None else _assignment_price_list_names(old.name),
	)
	new_doc.insert()
	return {"previous": _assignment_response(old), "current": _assignment_response(new_doc)}


def validate_branch_assignment(doc) -> None:
	controlled_relink = bool(getattr(doc.flags, "controlled_branch_setup_relink", False))
	if controlled_relink:
		if not doc.user or not frappe.db.exists("User", doc.user):
			frappe.throw(_("The linked User no longer exists."))
	else:
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
	_validate_assignment_price_list_immutability(doc)
	_validate_assignment_price_lists(doc)
	_lock_assignment_user(doc.user)
	start = getdate(doc.effective_from)
	end = getdate(doc.effective_to) if doc.effective_to else None
	if end and end < start:
		frappe.throw(_("Effective To cannot be before Effective From."))

	if not controlled_relink:
		profile = _validate_company_branch(doc.company, doc.branch)
		doc.branch_setup = profile.name
	doc.status = _status_for_dates(start, end)
	_validate_assignment_price_lists(doc)
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
	values = frappe.db.get_value("User", user, ["enabled", "user_type"])
	enabled, user_type = values if values else (0, "")
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
	if not getattr(doc.flags, "controlled_assignment_price_list_update", False):
		stored_price_lists = sorted(_assignment_price_list_names(doc.name))
		current_price_lists = sorted(_normalise_price_lists(getattr(doc, "allowed_price_lists", []) or []))
		if stored_price_lists != current_price_lists:
			changed.append("allowed_price_lists")
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
	values = {
		"user": user,
		"company": company,
		"exclude_name": exclude_name or "",
		"start": getdate(start),
		"end_bound": getdate(end) if end else date(9999, 12, 31),
	}
	if primary_only:
		rows = frappe.db.sql(
			"""
			select name
			from `tabRetailEdge Branch Assignment`
			where user = %(user)s
			  and company = %(company)s
			  and name != %(exclude_name)s
			  and is_primary = 1
			  and effective_from <= %(end_bound)s
			  and (effective_to is null or effective_to >= %(start)s)
			order by effective_from asc
			limit 1
			""",
			values,
			pluck=True,
		)
	else:
		values["branch"] = branch or ""
		rows = frappe.db.sql(
			"""
			select name
			from `tabRetailEdge Branch Assignment`
			where user = %(user)s
			  and company = %(company)s
			  and branch = %(branch)s
			  and name != %(exclude_name)s
			  and effective_from <= %(end_bound)s
			  and (effective_to is null or effective_to >= %(start)s)
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
	company = query_filters.get("company") or None
	if has_branch_assignments(user=user):
		branches = get_assignment_branches(user=user, company=company)
	else:
		allowed = get_user_allowed_branches(user=user, company=company)
		branches = [
			str(value or "").strip()
			for value in allowed.get("branches") or []
			if str(value or "").strip()
		]
	requested_branch = str(query_filters.get("branch") or "").strip()
	if requested_branch and requested_branch not in branches:
		query_filters["name"] = "__no_visible_branch_assignment__"
		return query_filters
	if branches:
		query_filters["branch"] = ["in", list(dict.fromkeys(branches))]
	else:
		query_filters["name"] = "__no_visible_branch_assignment__"
	return query_filters


def _normalise_price_lists(value) -> list[str]:
	if isinstance(value, str):
		value = frappe.parse_json(value)
	if not value:
		return []
	if not isinstance(value, list):
		frappe.throw(_("Allowed Price Lists must be a list."))
	result: list[str] = []
	seen: set[str] = set()
	for row in value:
		raw_name = row.get("price_list") if isinstance(row, dict) else getattr(row, "price_list", row)
		name = str(raw_name or "").strip()
		if not name or name in seen:
			continue
		seen.add(name)
		result.append(name)
	if len(result) > 50:
		frappe.throw(_("A Branch Assignment can contain at most 50 Price Lists."))
	return result


def _validate_price_list(name: str) -> None:
	row = frappe.db.get_value("Price List", name, ["enabled", "selling", "buying"], as_dict=True)
	if not row:
		frappe.throw(_("Price List {0} does not exist.").format(name))
	if not int(row.get("enabled") or 0):
		frappe.throw(_("Price List {0} is disabled.").format(name))
	if not (int(row.get("selling") or 0) or int(row.get("buying") or 0)):
		frappe.throw(_("Price List {0} must be enabled for Selling, Buying, or both.").format(name))
	if not frappe.has_permission("Price List", "read", doc=name):
		frappe.throw(_("You do not have permission to assign Price List {0}.").format(name), frappe.PermissionError)


def _validate_assignment_price_lists(doc) -> None:
	names = _normalise_price_lists(getattr(doc, "allowed_price_lists", []) or [])
	for name in names:
		_validate_price_list(name)


def _set_assignment_price_lists(doc, value) -> None:
	doc.set("allowed_price_lists", [])
	for name in _normalise_price_lists(value):
		_validate_price_list(name)
		doc.append("allowed_price_lists", {"price_list": name})


def _assignment_price_list_names(name: str) -> list[str]:
	if not name or not frappe.db.exists("DocType", "RetailEdge Branch Assignment Price List"):
		return []
	return [
		str(value or "").strip()
		for value in frappe.get_all(
			"RetailEdge Branch Assignment Price List",
			filters={
				"parent": name,
				"parenttype": "RetailEdge Branch Assignment",
				"parentfield": "allowed_price_lists",
			},
			pluck="price_list",
			order_by="idx asc",
			limit_page_length=0,
		)
		if str(value or "").strip()
	]


def _attach_assignment_price_lists(rows) -> list[dict[str, Any]]:
	result = [dict(row) for row in rows or []]
	names = [str(row.get("name") or "").strip() for row in result if row.get("name")]
	if not names or not frappe.db.exists("DocType", "RetailEdge Branch Assignment Price List"):
		for row in result:
			row["allowed_price_lists"] = []
		return result
	children = frappe.get_all(
		"RetailEdge Branch Assignment Price List",
		filters={
			"parent": ["in", names],
			"parenttype": "RetailEdge Branch Assignment",
			"parentfield": "allowed_price_lists",
		},
		fields=["parent", "price_list", "idx"],
		order_by="parent asc, idx asc",
		limit_page_length=0,
	)
	by_parent: dict[str, list[str]] = {}
	for child in children:
		price_list = str(child.get("price_list") or "").strip()
		if price_list:
			by_parent.setdefault(str(child.get("parent") or ""), []).append(price_list)
	for row in result:
		row["allowed_price_lists"] = by_parent.get(str(row.get("name") or ""), [])
	return result


def get_branch_assignment_price_lists(
	*,
	user: str | None = None,
	company: str | None = None,
	branch: str | None = None,
	as_of=None,
) -> dict[str, Any]:
	user = user or getattr(frappe.session, "user", None)
	branch = str(branch or "").strip()
	rows = get_active_branch_assignments(user=user, company=company, as_of=as_of)
	if branch:
		rows = [row for row in rows if str(row.get("branch") or "").strip() == branch]
	names: list[str] = []
	for row in rows:
		for name in row.get("allowed_price_lists") or []:
			if name and name not in names:
				names.append(name)
	return {
		"names": names,
		"restricted": bool(names),
		"assignment_names": [row.get("name") for row in rows if row.get("name")],
	}


@frappe.whitelist(methods=["POST"])
def update_branch_assignment_price_lists(name: str, allowed_price_lists=None) -> dict[str, Any]:
	doc = frappe.get_doc("RetailEdge Branch Assignment", name)
	doc.check_permission("write")
	status = _status_for_dates(
		getdate(doc.effective_from),
		getdate(doc.effective_to) if doc.effective_to else None,
	)
	if status == "Ended":
		frappe.throw(_("Ended Branch Assignment history cannot be changed."))
	_set_assignment_price_lists(doc, allowed_price_lists)
	doc.flags.controlled_assignment_price_list_update = True
	doc.save()
	return _assignment_response(doc)


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
		"allowed_price_lists": _assignment_price_list_names(doc.name)
		if getattr(doc, "name", None)
		else _normalise_price_lists(getattr(doc, "allowed_price_lists", []) or []),
	}


def _normalise_price_lists(values) -> list[str]:
	if values is None:
		return []
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, (list, tuple)):
		frappe.throw(_("Allowed Price Lists must be a list."))
	result = []
	for value in values:
		if isinstance(value, dict):
			value = value.get("price_list") or value.get("value") or value.get("name")
		name = str(value or "").strip()
		if name and name not in result:
			result.append(name)
	return result


def _price_lists_by_assignment(names: list[str]) -> dict[str, list[str]]:
	result = {str(name): [] for name in names if name}
	if not result or not frappe.db.exists("DocType", "RetailEdge Branch Assignment Price List"):
		return result
	rows = frappe.get_all(
		"RetailEdge Branch Assignment Price List",
		filters={
			"parent": ["in", list(result)],
			"parenttype": "RetailEdge Branch Assignment",
			"parentfield": "price_lists",
		},
		fields=["parent", "price_list"],
		order_by="parent asc, idx asc",
		limit_page_length=0,
	)
	for row in rows:
		parent = str(row.get("parent") or "")
		name = str(row.get("price_list") or "").strip()
		if parent in result and name and name not in result[parent]:
			result[parent].append(name)
	return result


def _validate_assignment_price_lists(doc) -> None:
	seen = set()
	for row in doc.price_lists or []:
		name = str(row.price_list or "").strip()
		if not name:
			continue
		if name in seen:
			frappe.throw(_("Price List {0} is repeated on this Branch Assignment.").format(name))
		seen.add(name)
		values = frappe.db.get_value("Price List", name, ["enabled", "selling", "buying"], as_dict=True)
		if not values:
			frappe.throw(_("Price List {0} does not exist.").format(name))
		if not int(values.get("enabled") or 0):
			frappe.throw(_("Price List {0} is disabled.").format(name))
		if not int(values.get("selling") or 0) and not int(values.get("buying") or 0):
			frappe.throw(_("Price List {0} must be a Selling or Buying Price List.").format(name))
		if not frappe.has_permission("Price List", "read", doc=name):
			frappe.throw(_("You do not have permission to assign Price List {0}.").format(name), frappe.PermissionError)


def _validate_assignment_price_list_immutability(doc) -> None:
	if (
		doc.is_new()
		or not doc.name
		or getattr(doc.flags, "controlled_assignment_update", False)
		or getattr(doc.flags, "controlled_price_list_update", False)
	):
		return
	if getattr(doc.flags, "controlled_branch_setup_relink", False):
		return
	stored = frappe.get_all(
		"RetailEdge Branch Assignment Price List",
		filters={"parent": doc.name, "parenttype": "RetailEdge Branch Assignment", "parentfield": "price_lists"},
		pluck="price_list",
		order_by="idx asc",
		limit_page_length=0,
	)
	current = [str(row.price_list or "").strip() for row in (doc.price_lists or []) if row.price_list]
	if list(stored or []) != current:
		frappe.throw(
			_("Saved Branch Assignment Price List history cannot be rewritten directly. Use Transfer to create a new effective-dated assignment.")
		)


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
