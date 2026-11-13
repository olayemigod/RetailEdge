from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from retailedge.branch_assignment import get_active_branch_assignments
from retailedge.setup_roles import ALL_RETAILEDGE_ROLE_NAMES, RETAILEDGE_ROLE_NAMES, canonicalize_retailedge_roles


SETUP_INCOMPLETE_MESSAGE = _(
	"Your RetailEdge access setup is not complete. Ask an administrator to assign your Company and Branch."
)
MAX_RECONCILIATION_PAGE_LENGTH = 100


def is_retailedge_operational_user(user: str | None = None) -> bool:
	user = str(user or getattr(frappe.session, "user", "") or "").strip()
	if not user or user == "Administrator":
		return False
	roles = canonicalize_retailedge_roles(frappe.get_roles(user))
	return bool(roles.intersection(RETAILEDGE_ROLE_NAMES))


def get_retailedge_user_readiness(
	user: str | None = None,
	company: str | None = None,
) -> dict[str, Any]:
	"""Return the governed operational-readiness contract for one RetailEdge user.

	ERPNext/Frappe roles and document permissions remain authoritative. RetailEdge
	adds only the product-specific orchestration needed to prove that a user with a
	RetailEdge role has an explicit, active Company/Branch assignment and usable
	Branch Setup. No assignment, User Permission or user default is created here.
	"""
	user = str(user or getattr(frappe.session, "user", "") or "").strip()
	company = str(company or "").strip()
	result = _base_result(user=user, company=company)
	if not user:
		return _block(result, "missing_user", _("Choose a User before checking access readiness."), "review_user")
	if user == "Administrator":
		result.update({"applicable": False, "ready": True, "status": "Ready", "message": ""})
		return result

	user_values = frappe.db.get_value("User", user, ["enabled", "user_type", "full_name"], as_dict=True)
	if not user_values:
		return _block(result, "missing_user", _("The selected User no longer exists."), "review_user")
	result["user_name"] = str(user_values.get("full_name") or user).strip()
	if not cint(user_values.get("enabled")):
		return _block(result, "user_disabled", _("Enable this User before activating RetailEdge access."), "review_user")
	if str(user_values.get("user_type") or "") != "System User":
		return _block(
			result,
			"not_system_user",
			_("RetailEdge operational access requires an enabled System User."),
			"review_user",
		)

	roles = canonicalize_retailedge_roles(frappe.get_roles(user))
	product_roles = sorted(roles.intersection(RETAILEDGE_ROLE_NAMES))
	result["roles"] = product_roles
	if not product_roles:
		result.update({"applicable": False, "ready": True, "status": "Not required", "message": ""})
		return result
	result["applicable"] = True

	all_assignments = list(get_active_branch_assignments(user=user))
	assignments = [row for row in all_assignments if not company or str(row.get("company") or "").strip() == company]
	result["active_assignment_count"] = len(assignments)
	result["active_companies"] = sorted(
		{
			str(row.get("company") or "").strip()
			for row in all_assignments
			if str(row.get("company") or "").strip()
		}
	)
	if company and company not in result["active_companies"]:
		_block(
			result,
			"missing_company_assignment",
			_("Assign this User to an active Branch in Company {0}.").format(company),
			"assign_branch",
		)
	elif not assignments:
		_block(
			result,
			"missing_branch_assignment",
			_("Assign this User to a Company and Branch before activating RetailEdge access."),
			"assign_branch",
		)
		return _finish(result)

	by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for row in assignments:
		assignment_company = str(row.get("company") or "").strip()
		if assignment_company:
			by_company[assignment_company].append(dict(row))

	valid_assignments: list[dict[str, Any]] = []
	for assignment_company, company_rows in sorted(by_company.items()):
		primary_rows = [row for row in company_rows if cint(row.get("is_primary"))]
		if len(company_rows) > 1 and len(primary_rows) != 1:
			_block(
				result,
				"primary_branch_required",
				_("Choose one Primary Branch for {0} so this User has a deterministic starting Branch.").format(
					assignment_company
				),
				"set_primary_branch",
			)
		for row in company_rows:
			if _validate_assignment(row=row, user=user, result=result):
				valid_assignments.append(row)

	result["valid_assignment_count"] = len(valid_assignments)
	result["assignments"] = [_assignment_summary(row) for row in assignments]
	result["starting_context"] = _resolve_starting_context(valid_assignments, user=user, requested_company=company)
	if assignments and not valid_assignments:
		_block(
			result,
			"no_usable_assignment",
			_("None of this User's active Branch Assignments currently resolves to usable RetailEdge access."),
			"review_assignment",
		)
	return _finish(result)


def assert_retailedge_user_ready(*, user: str | None = None, company: str | None = None) -> dict[str, Any]:
	readiness = get_retailedge_user_readiness(user=user, company=company)
	if readiness.get("applicable") and not readiness.get("ready"):
		message = readiness.get("message") or SETUP_INCOMPLETE_MESSAGE
		frappe.throw(message, frappe.PermissionError)
	return readiness


@frappe.whitelist()
def get_my_retailedge_user_readiness(company: str = "") -> dict[str, Any]:
	readiness = get_retailedge_user_readiness(user=frappe.session.user, company=company)
	readiness["can_repair"] = _can_repair_assignments()
	return readiness


@frappe.whitelist()
def get_retailedge_user_readiness_reconciliation(
	search: str = "",
	include_ready: int = 0,
	start: int = 0,
	page_length: int = 50,
) -> dict[str, Any]:
	"""Return a complete, non-mutating readiness review of users with RetailEdge roles.

	The eligible population is evaluated before response pagination so historical
	users with incomplete setup remain discoverable without an arbitrary data cap.
	No Branch Assignment, User Permission or default is written by this method.
	"""
	_assert_reconciliation_access()
	search = str(search or "").strip().lower()
	start = max(cint(start), 0)
	page_length = min(max(cint(page_length) or 50, 1), MAX_RECONCILIATION_PAGE_LENGTH)
	include_ready = bool(cint(include_ready))

	role_rows = frappe.get_all(
		"Has Role",
		filters={"parenttype": "User", "role": ["in", list(ALL_RETAILEDGE_ROLE_NAMES)]},
		pluck="parent",
		limit_page_length=0,
	)
	users = sorted({str(user or "").strip() for user in role_rows if str(user or "").strip()})
	rows: list[dict[str, Any]] = []
	ready_count = 0
	incomplete_count = 0
	for user in users:
		user_values = frappe.db.get_value("User", user, ["full_name", "email"], as_dict=True) or {}
		searchable = " ".join(
			[
				user,
				str(user_values.get("full_name") or ""),
				str(user_values.get("email") or ""),
			]
		).lower()
		if search and search not in searchable:
			continue
		readiness = get_retailedge_user_readiness(user=user)
		if readiness.get("ready"):
			ready_count += 1
		else:
			incomplete_count += 1
		if readiness.get("ready") and not include_ready:
			continue
		rows.append(
			{
				"user": user,
				"user_name": str(user_values.get("full_name") or user),
				"status": readiness.get("status"),
				"ready": bool(readiness.get("ready")),
				"roles": list(readiness.get("roles") or []),
				"active_assignment_count": cint(readiness.get("active_assignment_count")),
				"active_companies": list(readiness.get("active_companies") or []),
				"message": readiness.get("message") or "",
				"reasons": list(readiness.get("reasons") or []),
				"repair_action": _first_repair_action(readiness),
			}
		)

	page = rows[start : start + page_length]
	return {
		"rows": page,
		"total": len(rows),
		"start": start,
		"page_length": page_length,
		"has_more": start + page_length < len(rows),
		"ready_count": ready_count,
		"incomplete_count": incomplete_count,
		"can_repair": _can_repair_assignments(),
	}


def _base_result(*, user: str, company: str) -> dict[str, Any]:
	return {
		"user": user,
		"user_name": user,
		"company": company,
		"applicable": False,
		"ready": False,
		"status": "Setup incomplete",
		"message": SETUP_INCOMPLETE_MESSAGE,
		"roles": [],
		"active_assignment_count": 0,
		"valid_assignment_count": 0,
		"active_companies": [],
		"assignments": [],
		"starting_context": {},
		"reasons": [],
	}


def _block(result: dict[str, Any], code: str, message: str, repair: str) -> dict[str, Any]:
	if not any(reason.get("code") == code and reason.get("message") == message for reason in result["reasons"]):
		result["reasons"].append({"code": code, "message": message, "repair": repair})
	result["ready"] = False
	result["status"] = "Setup incomplete"
	result["message"] = result["reasons"][0]["message"] if result["reasons"] else SETUP_INCOMPLETE_MESSAGE
	return result


def _finish(result: dict[str, Any]) -> dict[str, Any]:
	if result.get("applicable") and not result.get("reasons"):
		result["ready"] = True
		result["status"] = "Ready"
		result["message"] = ""
	elif result.get("applicable"):
		result["ready"] = False
		result["status"] = "Setup incomplete"
		result["message"] = result["reasons"][0]["message"] if result["reasons"] else SETUP_INCOMPLETE_MESSAGE
	return result


def _validate_assignment(*, row: dict[str, Any], user: str, result: dict[str, Any]) -> bool:
	company = str(row.get("company") or "").strip()
	branch = str(row.get("branch") or "").strip()
	if not company or not branch:
		_block(
			result,
			"invalid_assignment_context",
			_("A current Branch Assignment is missing its Company or Branch."),
			"review_assignment",
		)
		return False
	profile = frappe.db.get_value(
		"RetailEdge Branch Profile",
		{"company": company, "branch": branch, "enabled": 1},
		["name", "default_pos_profile"],
		as_dict=True,
	)
	if not profile:
		_block(
			result,
			"branch_setup_disabled",
			_("Enable Branch Setup for {0} in {1} before this assignment can be used.").format(branch, company),
			"open_branch_setup",
		)
		return False
	if not _has_document_read("Company", company, user=user):
		_block(
			result,
			"company_permission_missing",
			_("This User does not have the minimum read access required for Company {0}.").format(company),
			"review_permissions",
		)
		return False
	if not _has_document_read("Branch", branch, user=user):
		_block(
			result,
			"branch_permission_missing",
			_("This User does not have the minimum read access required for Branch {0}.").format(branch),
			"review_permissions",
		)
		return False
	if not _validate_pos_readiness(
		user=user,
		company=company,
		branch=branch,
		default_pos_profile=str(profile.get("default_pos_profile") or "").strip(),
		result=result,
	):
		return False
	return True


def _validate_pos_readiness(
	*,
	user: str,
	company: str,
	branch: str,
	default_pos_profile: str,
	result: dict[str, Any],
) -> bool:
	if not frappe.db.exists("DocType", "POS Profile User"):
		return True
	assigned_rows = frappe.get_all(
		"POS Profile User",
		filters={"user": user, "parenttype": "POS Profile"},
		fields=["parent"],
		limit_page_length=0,
	)
	assigned_profiles = {str(row.get("parent") or "").strip() for row in assigned_rows if row.get("parent")}
	if not assigned_profiles:
		return True
	if not default_pos_profile:
		_block(
			result,
			"pos_profile_missing",
			_("Configure a POS Profile in Branch Setup for {0} before this User can use POS there.").format(branch),
			"configure_pos_profile",
		)
		return False

	profile = frappe.db.get_value("POS Profile", default_pos_profile, ["company", "disabled"], as_dict=True)
	if not profile or cint(profile.get("disabled")):
		_block(
			result,
			"pos_profile_unavailable",
			_("The POS Profile configured for Branch {0} is unavailable or disabled.").format(branch),
			"configure_pos_profile",
		)
		return False
	if str(profile.get("company") or "").strip() and str(profile.get("company") or "").strip() != company:
		_block(
			result,
			"pos_profile_company_mismatch",
			_("The POS Profile configured for Branch {0} belongs to another Company.").format(branch),
			"configure_pos_profile",
		)
		return False
	if not _has_document_read("POS Profile", default_pos_profile, user=user):
		_block(
			result,
			"pos_profile_permission_missing",
			_("This User does not have permission to use the POS Profile configured for Branch {0}.").format(branch),
			"review_permissions",
		)
		return False

	# ERPNext treats a POS Profile with no Applicable for Users rows as shared.
	# A User may have an explicit assignment to another Profile and still be allowed
	# to use this Branch's shared default Profile. Do not falsely require an
	# explicit row merely because another Profile is restricted for that User.
	default_profile_is_restricted = bool(
		frappe.db.exists(
			"POS Profile User",
			{"parent": default_pos_profile, "parenttype": "POS Profile"},
		)
	)
	if not default_profile_is_restricted:
		return True
	if default_pos_profile not in assigned_profiles:
		_block(
			result,
			"pos_profile_not_assigned",
			_("Assign this User to the POS Profile configured for Branch {0}.").format(branch),
			"configure_pos_profile",
		)
		return False
	return True


def _has_document_read(doctype: str, name: str, *, user: str) -> bool:
	previous_messages = list(getattr(frappe.local, "message_log", []) or [])
	try:
		return bool(frappe.has_permission(doctype, "read", doc=name, user=user))
	except Exception:
		return False
	finally:
		frappe.local.message_log = previous_messages


def _resolve_starting_context(
	assignments: list[dict[str, Any]],
	*,
	user: str,
	requested_company: str,
) -> dict[str, str]:
	if not assignments:
		return {}
	rows = [row for row in assignments if not requested_company or row.get("company") == requested_company]
	if not rows:
		return {}
	if requested_company:
		primary = [row for row in rows if cint(row.get("is_primary"))]
		candidate = primary[0] if len(primary) == 1 else (rows[0] if len(rows) == 1 else None)
		return _assignment_context(candidate) if candidate else {}

	default_company = str(frappe.defaults.get_user_default("Company", user=user) or "").strip()
	if default_company:
		company_rows = [row for row in rows if str(row.get("company") or "").strip() == default_company]
		primary = [row for row in company_rows if cint(row.get("is_primary"))]
		candidate = primary[0] if len(primary) == 1 else (company_rows[0] if len(company_rows) == 1 else None)
		if candidate:
			return _assignment_context(candidate)
	companies = sorted({str(row.get("company") or "").strip() for row in rows if row.get("company")})
	if len(companies) == 1:
		company_rows = [row for row in rows if str(row.get("company") or "").strip() == companies[0]]
		primary = [row for row in company_rows if cint(row.get("is_primary"))]
		candidate = primary[0] if len(primary) == 1 else (company_rows[0] if len(company_rows) == 1 else None)
		if candidate:
			return _assignment_context(candidate)
	return {}


def _assignment_context(row: dict[str, Any] | None) -> dict[str, str]:
	if not row:
		return {}
	return {
		"company": str(row.get("company") or "").strip(),
		"branch": str(row.get("branch") or "").strip(),
		"assignment": str(row.get("name") or "").strip(),
	}


def _assignment_summary(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"name": row.get("name"),
		"company": row.get("company"),
		"branch": row.get("branch"),
		"branch_role": row.get("branch_role"),
		"is_primary": cint(row.get("is_primary")),
		"effective_from": row.get("effective_from"),
		"effective_to": row.get("effective_to"),
	}


def _first_repair_action(readiness: dict[str, Any]) -> dict[str, str]:
	reasons = readiness.get("reasons") or []
	if not reasons:
		return {}
	repair = str(reasons[0].get("repair") or "review_assignment")
	labels = {
		"assign_branch": _("Assign Company and Branch"),
		"set_primary_branch": _("Choose Primary Branch"),
		"open_branch_setup": _("Open Branch Setup"),
		"configure_pos_profile": _("Review POS Setup"),
		"review_permissions": _("Review Permissions"),
		"review_user": _("Review User"),
		"review_assignment": _("Review Branch Assignment"),
	}
	return {"key": repair, "label": labels.get(repair, _("Review Setup"))}


def _can_repair_assignments() -> bool:
	try:
		return bool(frappe.has_permission("RetailEdge Branch Assignment", "create"))
	except Exception:
		return False


def _assert_reconciliation_access() -> None:
	if not frappe.has_permission("RetailEdge Branch Assignment", "read"):
		frappe.throw(_("You do not have permission to review RetailEdge user access setup."), frappe.PermissionError)
	if not frappe.has_permission("User", "read"):
		frappe.throw(_("You do not have permission to review User access setup."), frappe.PermissionError)
