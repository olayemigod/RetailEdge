from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.branch_context import (
	get_user_allowed_branches,
	resolve_branch_from_opening_shift,
	resolve_branch_from_pos_profile,
	resolve_branch_from_user,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.branch_profile import get_branch_profile_defaults

OPERATING_CONTEXT_TTL_SECONDS = 12 * 60 * 60
OPERATING_CONTEXT_CACHE_PREFIX = "retailedge:operating-context"


@frappe.whitelist()
def get_operating_context(company: str = "") -> dict[str, Any]:
	"""Return the current session-scoped operating Company/Branch context.

	The operating context guides new work only. Existing documents continue to use
	their stored Company/Branch/Warehouse truth and are never rewritten from this
	selection.
	"""
	user = frappe.session.user
	requested_company = _clean(company)
	cached = _read_cached_context(user=user)

	if cached:
		validated = _validate_context(
			company=_clean(cached.get("company")),
			branch=_clean(cached.get("branch")),
			user=user,
			throw=False,
		)
		if validated.get("allowed"):
			if not requested_company or validated.get("company") == requested_company:
				return _build_context(
					company=validated.get("company") or "",
					branch=validated.get("branch") or "",
					user=user,
					source="session",
				)
		else:
			_clear_cached_context(user=user)

	fallback_company = requested_company or _clean(frappe.defaults.get_user_default("Company"))
	if fallback_company:
		_assert_company_access(fallback_company)

	resolved = resolve_branch_from_user(user=user, company=fallback_company or None)
	fallback_branch = _clean(resolved.get("branch"))
	fallback_company = _clean(resolved.get("company")) or fallback_company
	if fallback_branch and fallback_company:
		validated = _validate_context(
			company=fallback_company,
			branch=fallback_branch,
			user=user,
			throw=False,
		)
		if validated.get("allowed"):
			return _build_context(
				company=fallback_company,
				branch=fallback_branch,
				user=user,
				source=resolved.get("source") or "fallback",
			)

	return _build_context(
		company=fallback_company,
		branch="",
		user=user,
		source="company_default" if fallback_company else "empty",
	)


@frappe.whitelist()
def get_allowed_operating_contexts(company: str = "") -> dict[str, Any]:
	"""Return permission-aware Companies and Branches for the switcher.

	Queries remain bounded and do not preload unrelated masters. Previewing Branch
	options for another Company never changes the active session context.
	"""
	user = frappe.session.user
	requested_company = _clean(company)
	companies = _allowed_companies()
	if requested_company and requested_company not in companies:
		frappe.throw(_("You do not have access to Company {0}.").format(requested_company), frappe.PermissionError)

	current = get_operating_context()
	selected_company = requested_company or _clean(current.get("company")) or _clean(frappe.defaults.get_user_default("Company"))
	if selected_company not in companies:
		selected_company = companies[0] if len(companies) == 1 else ""

	branches = _allowed_branches(company=selected_company, user=user) if selected_company else []
	return {
		"companies": companies,
		"branches": branches,
		"selected_company": selected_company,
		"current": current,
		"can_switch_company": len(companies) > 1,
		"can_switch_branch": len(branches) > 1,
		"switch_blockers": _get_switch_blockers(user=user),
	}


@frappe.whitelist()
def switch_operating_context(company: str, branch: str) -> dict[str, Any]:
	"""Switch the user's operating context after server-side validation."""
	user = frappe.session.user
	company = _clean(company)
	branch = _clean(branch)
	if not company:
		frappe.throw(_("Company is required."))
	if not branch:
		frappe.throw(_("Branch is required."))

	validated = _validate_context(company=company, branch=branch, user=user, throw=True)
	_assert_switch_safe(company=validated["company"], branch=validated["branch"], user=user)
	context = _build_context(
		company=validated["company"],
		branch=validated["branch"],
		user=user,
		source="session",
	)
	_write_cached_context(context, user=user)
	return context


@frappe.whitelist()
def clear_operating_context() -> dict[str, Any]:
	"""Clear only the session override and return the normal fallback context."""
	_clear_cached_context(user=frappe.session.user)
	return get_operating_context()


def get_effective_operating_context(company: str = "", branch: str = "") -> dict[str, Any]:
	"""Internal helper for new-document/default flows.

	Explicit arguments win. Session context is used only when the caller has not
	already supplied Company/Branch truth.
	"""
	explicit_company = _clean(company)
	explicit_branch = _clean(branch)
	if explicit_company and explicit_branch:
		validated = _validate_context(
			company=explicit_company,
			branch=explicit_branch,
			user=frappe.session.user,
			throw=True,
		)
		return _build_context(
			company=validated["company"],
			branch=validated["branch"],
			user=frappe.session.user,
			source="explicit",
		)

	current = get_operating_context(company=explicit_company)
	if explicit_branch:
		validated = _validate_context(
			company=explicit_company or current.get("company") or "",
			branch=explicit_branch,
			user=frappe.session.user,
			throw=True,
		)
		return _build_context(
			company=validated["company"],
			branch=validated["branch"],
			user=frappe.session.user,
			source="explicit_branch",
		)
	return current


def _build_context(*, company: str, branch: str, user: str, source: str) -> dict[str, Any]:
	defaults = get_branch_profile_defaults(company=company or None, branch=branch or None, user=user) if company and branch else {}
	return {
		"company": company or "",
		"branch": branch or "",
		"source": source,
		"defaults": defaults,
		"default_pos_profile": defaults.get("default_pos_profile") or "",
		"default_stock_location": defaults.get("default_warehouse") or "",
		"default_source_stock_location": defaults.get("default_source_warehouse") or "",
		"default_destination_stock_location": defaults.get("default_target_warehouse") or "",
	}


def _validate_context(*, company: str, branch: str, user: str, throw: bool) -> dict[str, Any]:
	company = _clean(company)
	branch = _clean(branch)
	if not company or not branch:
		result = {"allowed": False, "company": company, "branch": branch, "reason": "missing_context"}
		if throw:
			frappe.throw(_("Company and Branch are required."))
		return result

	try:
		_assert_company_access(company)
		_assert_branch_exists_and_active(branch)
		branch_company = _branch_company(branch)
		if branch_company and branch_company != company:
			frappe.throw(_("Branch {0} does not belong to Company {1}.").format(branch, company))
		validate_user_branch_access(branch, user=user, company=company, throw=True)
		if branch not in _allowed_branches(company=company, user=user):
			frappe.throw(_("You do not have access to Branch {0}.").format(branch), frappe.PermissionError)
		return {"allowed": True, "company": company, "branch": branch, "reason": "validated"}
	except Exception:
		if throw:
			raise
		return {"allowed": False, "company": company, "branch": branch, "reason": "validation_failed"}


def _get_switch_blockers(*, user: str) -> list[dict[str, str]]:
	"""Return server-detectable blockers without changing state.

	Open POSNext and ERPNext POS sessions are authoritative server evidence that
	branch-bound cashier work is active. Browser cart/payment guards are layered on
	top because unsaved cart state is not server truth yet.
	"""
	blockers: list[dict[str, str]] = []
	try:
		from retailedge.cashier_context import find_open_pos_opening_shift

		opening_shift = find_open_pos_opening_shift(user=user)
	except Exception:
		opening_shift = None
	if opening_shift:
		shift_company = _clean(getattr(opening_shift, "company", None))
		resolved = resolve_branch_from_opening_shift(opening_shift, company=shift_company or None)
		blockers.append(
			{
				"code": "open_pos_shift",
				"message": _("Close the active POS shift before switching to another operating context."),
				"company": shift_company,
				"branch": _clean(resolved.get("branch")),
				"reference": _clean(getattr(opening_shift, "name", None)),
			}
		)

	opening_entry = _find_open_erpnext_pos_opening(user=user)
	if opening_entry:
		entry_company = _clean(opening_entry.get("company"))
		profile = _clean(opening_entry.get("pos_profile"))
		resolved = resolve_branch_from_pos_profile(profile, company=entry_company or None) if profile else {}
		blockers.append(
			{
				"code": "open_erpnext_pos",
				"message": _("Close the active POS Opening Entry before switching to another operating context."),
				"company": entry_company,
				"branch": _clean(resolved.get("branch")),
				"reference": _clean(opening_entry.get("name")),
			}
		)
	return blockers


def _find_open_erpnext_pos_opening(*, user: str) -> dict[str, Any] | None:
	if not frappe.db.exists("DocType", "POS Opening Entry"):
		return None
	try:
		meta = frappe.get_meta("POS Opening Entry")
	except Exception:
		return None
	filters: dict[str, Any] = {"docstatus": ["in", [0, 1]]}
	if meta.has_field("user"):
		filters["user"] = user
	elif meta.has_field("owner"):
		filters["owner"] = user
	if meta.has_field("status"):
		filters["status"] = ["in", ["Open", "Opened"]]
	fields = ["name"]
	for fieldname in ("company", "pos_profile", "status"):
		if meta.has_field(fieldname):
			fields.append(fieldname)
	try:
		rows = frappe.get_list(
			"POS Opening Entry",
			filters=filters,
			fields=fields,
			order_by="creation desc",
			limit_page_length=1,
		)
	except Exception:
		rows = []
	return dict(rows[0]) if rows else None


def _assert_switch_safe(*, company: str, branch: str, user: str) -> None:
	for blocker in _get_switch_blockers(user=user):
		blocker_company = _clean(blocker.get("company"))
		blocker_branch = _clean(blocker.get("branch"))
		if blocker_company and blocker_company != company:
			frappe.throw(blocker["message"])
		if not blocker_branch or blocker_branch != branch:
			frappe.throw(blocker["message"])


def _allowed_companies() -> list[str]:
	try:
		rows = frappe.get_list(
			"Company",
			fields=["name"],
			order_by="name asc",
			limit_page_length=100,
		)
	except Exception:
		rows = []
	return [_clean(row.get("name")) for row in rows if _clean(row.get("name"))]


def _allowed_branches(*, company: str, user: str) -> list[str]:
	company = _clean(company)
	if not company:
		return []
	filters: dict[str, Any] = {}
	if _doctype_has_field("Branch", "company"):
		filters["company"] = company
	if _doctype_has_field("Branch", "disabled"):
		filters["disabled"] = 0
	try:
		rows = frappe.get_list(
			"Branch",
			filters=filters,
			fields=["name"],
			order_by="name asc",
			limit_page_length=200,
		)
	except Exception:
		rows = []
	permission_visible = [_clean(row.get("name")) for row in rows if _clean(row.get("name"))]
	if user_has_global_branch_access(user=user):
		return permission_visible

	restricted = set(get_user_allowed_branches(user=user, company=company).get("branches") or [])
	if not restricted:
		return permission_visible
	return [branch for branch in permission_visible if branch in restricted]


def _assert_company_access(company: str) -> None:
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have access to Company {0}.").format(company), frappe.PermissionError)


def _assert_branch_exists_and_active(branch: str) -> None:
	if not frappe.db.exists("Branch", branch):
		frappe.throw(_("Branch {0} does not exist.").format(branch))
	if not frappe.has_permission("Branch", "read", doc=branch):
		frappe.throw(_("You do not have access to Branch {0}.").format(branch), frappe.PermissionError)
	if _doctype_has_field("Branch", "disabled") and frappe.db.get_value("Branch", branch, "disabled"):
		frappe.throw(_("Branch {0} is disabled.").format(branch))


def _branch_company(branch: str) -> str:
	if not _doctype_has_field("Branch", "company"):
		return ""
	return _clean(frappe.db.get_value("Branch", branch, "company"))


def _doctype_has_field(doctype: str, fieldname: str) -> bool:
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def _cache_key(*, user: str) -> str:
	sid = _clean(getattr(frappe.session, "sid", "")) or "session"
	return f"{OPERATING_CONTEXT_CACHE_PREFIX}:{user}:{sid}"


def _read_cached_context(*, user: str) -> dict[str, Any]:
	try:
		value = frappe.cache.get_value(_cache_key(user=user))
		return value if isinstance(value, dict) else {}
	except Exception:
		return {}


def _write_cached_context(context: dict[str, Any], *, user: str) -> None:
	frappe.cache.set_value(
		_cache_key(user=user),
		{"company": context.get("company") or "", "branch": context.get("branch") or ""},
		expires_in_sec=OPERATING_CONTEXT_TTL_SECONDS,
	)


def _clear_cached_context(*, user: str) -> None:
	try:
		frappe.cache.delete_value(_cache_key(user=user))
	except Exception:
		return


def _clean(value: Any) -> str:
	return str(value or "").strip()
