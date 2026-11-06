from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, nowdate

from retailedge.branch_assignment import ROLE_TYPES, create_branch_assignment, get_active_branch_assignments
from retailedge.branch_assignment_ui import search_branch_assignment_options
from retailedge.branch_profile import get_exact_branch_profile
from retailedge.setup_roles import RETAILEDGE_ROLE_NAMES, canonicalize_retailedge_roles
from retailedge.user_readiness import get_retailedge_user_readiness


PERSONAS = (
	{
		"value": "RetailEdgeCashier",
		"label": "Cashier",
		"description": "Sell at the point of sale and work within assigned Branches.",
		"branch_role": "Cashier",
		"pos_default": True,
	},
	{
		"value": "RetailEdgeBranchManager",
		"label": "Branch Manager",
		"description": "Manage day-to-day activity for assigned Branches.",
		"branch_role": "Manager",
		"pos_default": False,
	},
	{
		"value": "RetailEdgeManager",
		"label": "Retail Manager",
		"description": "Manage RetailEdge operations across the permitted business scope.",
		"branch_role": "Manager",
		"pos_default": False,
	},
	{
		"value": "RetailEdgeAuditor",
		"label": "Auditor",
		"description": "Review permitted RetailEdge records without operational posting authority.",
		"branch_role": "Auditor",
		"pos_default": False,
	},
)
PERSONA_BY_ROLE = {row["value"]: row for row in PERSONAS}
MAX_LINK_RESULTS = 20


def _assert_onboarding_read() -> None:
	if not frappe.has_permission("User", "read"):
		frappe.throw(_("You do not have permission to review Users."), frappe.PermissionError)
	if not frappe.has_permission("RetailEdge Branch Assignment", "read"):
		frappe.throw(_("You do not have permission to review Branch Assignments."), frappe.PermissionError)


def _assert_assignment_create() -> None:
	if not frappe.has_permission("RetailEdge Branch Assignment", "create"):
		frappe.throw(_("You do not have permission to create Branch Assignments."), frappe.PermissionError)


def _user_summary(user: str) -> dict[str, Any]:
	if not user:
		return {}
	doc = frappe.get_doc("User", user)
	doc.check_permission("read")
	roles = canonicalize_retailedge_roles(row.role for row in (doc.get("roles") or []))
	return {
		"name": doc.name,
		"email": doc.email,
		"full_name": doc.full_name or doc.name,
		"enabled": bool(cint(doc.enabled)),
		"user_type": doc.user_type or "",
		"retailedge_roles": sorted(role for role in roles if role in RETAILEDGE_ROLE_NAMES),
		"has_role_profiles": bool(doc.get("role_profiles")),
		"can_write": bool(frappe.has_permission("User", "write", doc=doc)),
		"readiness": get_retailedge_user_readiness(user=doc.name),
	}


def _profile_summary(*, company: str, branch: str, user: str = "") -> dict[str, Any]:
	if not company or not branch:
		return {"configured": False, "pos_required_supported": False}
	profile = get_exact_branch_profile(company=company, branch=branch, active_only=True)
	if not profile:
		return {
			"configured": False,
			"pos_required_supported": False,
			"message": _("Configure Branch Setup for {0} in {1} before onboarding a User there.").format(
				branch, company
			),
		}
	if not frappe.has_permission("RetailEdge Branch Profile", "read", doc=profile):
		frappe.throw(_("You do not have permission to view this Branch Setup."), frappe.PermissionError)

	result = {
		"configured": True,
		"branch_setup": profile.name,
		"company": company,
		"branch": branch,
		"default_pos_profile": str(profile.get("default_pos_profile") or "").strip(),
		"pos_required_supported": False,
		"pos_access_mode": "not_configured",
		"pos_assigned": False,
		"pos_default": False,
		"can_manage_pos_profile": False,
	}
	pos_profile_name = result["default_pos_profile"]
	if not pos_profile_name:
		return result

	# POS is conditional. A non-POS User must not be blocked merely because the
	# setup operator cannot read POS Profile details.
	if not frappe.has_permission("POS Profile", "read", doc=pos_profile_name):
		result.update(
			{
				"pos_access_mode": "unavailable",
				"pos_message": _("You do not have permission to review the Branch POS Profile."),
			}
		)
		return result

	pos_doc = frappe.get_doc("POS Profile", pos_profile_name)
	rows = list(pos_doc.get("applicable_for_users") or [])
	matching = [row for row in rows if str(row.user or "").strip() == user] if user else []
	result.update(
		{
			"pos_required_supported": not bool(cint(pos_doc.disabled)) and str(pos_doc.company or "").strip() == company,
			"pos_access_mode": "restricted" if rows else "shared",
			"pos_assigned": bool(matching),
			"pos_default": any(bool(cint(row.default)) for row in matching),
			"can_manage_pos_profile": bool(frappe.has_permission("POS Profile", "write", doc=pos_doc)),
			"pos_profile_disabled": bool(cint(pos_doc.disabled)),
		}
	)
	return result


@frappe.whitelist()
def get_user_onboarding_context(user: str = "") -> dict[str, Any]:
	"""Return the permission-aware context used by the RetailEdge onboarding wizard."""
	_assert_onboarding_read()
	user = str(user or "").strip()
	return {
		"personas": list(PERSONAS),
		"branch_roles": sorted(ROLE_TYPES),
		"today": nowdate(),
		"permissions": {
			"can_create_user": bool(frappe.has_permission("User", "create")),
			"can_create_assignment": bool(frappe.has_permission("RetailEdge Branch Assignment", "create")),
		},
		"selected_user": _user_summary(user) if user else {},
	}


@frappe.whitelist()
def get_user_onboarding_branch_context(company: str = "", branch: str = "", user: str = "") -> dict[str, Any]:
	"""Return exact Company -> Branch setup and conditional POS applicability."""
	_assert_onboarding_read()
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	user = str(user or "").strip()
	return _profile_summary(company=company, branch=branch, user=user)


@frappe.whitelist()
def search_user_onboarding_options(
	fieldname: str,
	txt: str = "",
	values=None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	"""Reuse the permission-aware Branch Assignment Link searches for onboarding."""
	_assert_onboarding_read()
	if fieldname not in {"user", "company", "branch"}:
		frappe.throw(_("Unsupported onboarding search field: {0}").format(fieldname))
	return search_branch_assignment_options(fieldname=fieldname, txt=txt, values=values, limit=limit)


def _parse_payload(payload) -> dict[str, Any]:
	values = frappe.parse_json(payload) if isinstance(payload, str) else dict(payload or {})
	mode = str(values.get("mode") or "existing").strip().lower()
	if mode not in {"existing", "new"}:
		frappe.throw(_("Choose whether to use an existing User or create a new User."))
	role = str(values.get("role") or "").strip()
	if role not in RETAILEDGE_ROLE_NAMES:
		frappe.throw(_("Choose a valid RetailEdge access role."))
	branch_role = str(values.get("branch_role") or PERSONA_BY_ROLE[role]["branch_role"]).strip()
	if branch_role not in ROLE_TYPES:
		frappe.throw(_("Choose a valid Branch responsibility."))
	company = str(values.get("company") or "").strip()
	branch = str(values.get("branch") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	if not branch:
		frappe.throw(_("Branch is required."))
	values.update(
		{
			"mode": mode,
			"role": role,
			"branch_role": branch_role,
			"company": company,
			"branch": branch,
			"effective_from": values.get("effective_from") or nowdate(),
			"is_primary": 1 if cint(values.get("is_primary")) else 0,
			"requires_pos": 1 if cint(values.get("requires_pos")) else 0,
			"send_welcome_email": 1 if cint(values.get("send_welcome_email")) else 0,
		}
	)
	return values


def _resolve_or_create_user(values: dict[str, Any]):
	if values["mode"] == "existing":
		user = str(values.get("user") or "").strip()
		if not user:
			frappe.throw(_("Choose an existing User."))
		doc = frappe.get_doc("User", user)
		doc.check_permission("write")
		if not cint(doc.enabled):
			frappe.throw(_("Enable this User before completing RetailEdge onboarding."))
		if str(doc.user_type or "") != "System User":
			frappe.throw(_("This account cannot be used for RetailEdge operations. Convert it to a staff account before continuing."))
		return doc, False

	if not frappe.has_permission("User", "create"):
		frappe.throw(_("You do not have permission to create Users."), frappe.PermissionError)
	email = str(values.get("email") or "").strip().lower()
	first_name = str(values.get("first_name") or "").strip()
	last_name = str(values.get("last_name") or "").strip()
	if not email:
		frappe.throw(_("Email is required for a new User."))
	if not first_name:
		frappe.throw(_("First Name is required for a new User."))
	if frappe.db.exists("User", email):
		frappe.throw(_("A User already exists with email {0}. Choose Existing User instead.").format(email))
	doc = frappe.new_doc("User")
	doc.email = email
	doc.first_name = first_name
	doc.last_name = last_name or None
	doc.enabled = 1
	doc.user_type = "System User"
	# Invitation is deliberately sent only after the complete governed setup succeeds.
	doc.send_welcome_email = 0
	doc.insert()
	return doc, True


def _ensure_retailedge_role(user_doc, role: str) -> bool:
	current = canonicalize_retailedge_roles(row.role for row in (user_doc.get("roles") or []))
	if role in current:
		return False
	if user_doc.get("role_profiles"):
		frappe.throw(
			_(
				"This User is governed by a Role Profile that does not include {0}. Update the Role Profile before continuing."
			).format(PERSONA_BY_ROLE[role]["label"])
		)
	user_doc.append("roles", {"role": role})
	user_doc.save()
	return True


def _ensure_branch_assignment(*, user: str, values: dict[str, Any]) -> tuple[str, bool]:
	active = list(get_active_branch_assignments(user=user, company=values["company"]))
	matching = [row for row in active if str(row.get("branch") or "").strip() == values["branch"]]
	if matching:
		if len(matching) != 1:
			frappe.throw(
				_(
					"This User has multiple active assignments for {0}. Review Branch Assignments before continuing."
				).format(values["branch"])
			)
		existing = matching[0]
		matches_responsibility = str(existing.get("branch_role") or "Other").strip() == values["branch_role"]
		matches_primary = bool(cint(existing.get("is_primary"))) == bool(cint(values["is_primary"]))
		if not (matches_responsibility and matches_primary):
			frappe.throw(
				_(
					"This User already has active access to {0}, but its Branch responsibility or Primary Branch setting differs. Use Branch Assignments to change it without rewriting history."
				).format(values["branch"])
			)
		return str(existing.get("name") or ""), False
	if active:
		frappe.throw(
			_(
				"This User already has active Branch access in {0}. Use Branch Assignments to add or transfer Branch access without rewriting history."
			).format(values["company"])
		)
	_assert_assignment_create()
	result = create_branch_assignment(
		user=user,
		company=values["company"],
		branch=values["branch"],
		effective_from=values["effective_from"],
		branch_role=values["branch_role"],
		is_primary=values["is_primary"],
		transfer_reason=_("Initial RetailEdge onboarding"),
	)
	return str(result.get("name") or ""), True


def _ensure_pos_access(*, user: str, company: str, branch: str) -> dict[str, Any]:
	context = _profile_summary(company=company, branch=branch, user=user)
	if not context.get("configured"):
		frappe.throw(context.get("message") or _("Branch Setup is required before POS access can be configured."))
	profile_name = str(context.get("default_pos_profile") or "").strip()
	if not profile_name:
		frappe.throw(_("Configure a default POS Profile in Branch Setup before assigning POS access."))
	if not context.get("pos_required_supported"):
		frappe.throw(context.get("pos_message") or _("The Branch POS Profile is disabled or belongs to another Company."))
	if context.get("pos_access_mode") == "shared":
		# ERPNext intentionally treats an empty Applicable for Users table as shared.
		# Do not add the first row here because that would silently revoke access for
		# every other current user of the Profile.
		return {**context, "changed": False, "access": "shared"}
	if context.get("pos_assigned") and context.get("pos_default"):
		return {**context, "changed": False, "access": "assigned"}

	pos_doc = frappe.get_doc("POS Profile", profile_name)
	pos_doc.check_permission("write")
	matching = [row for row in (pos_doc.get("applicable_for_users") or []) if str(row.user or "").strip() == user]
	if matching:
		matching[0].default = 1
	else:
		pos_doc.append("applicable_for_users", {"user": user, "default": 1})
	# ERPNext's POS Profile controller validates one default Profile per User/Company.
	pos_doc.save()
	return {**_profile_summary(company=company, branch=branch, user=user), "changed": True, "access": "assigned"}


@frappe.whitelist(methods=["POST"])
def complete_user_onboarding(payload=None) -> dict[str, Any]:
	"""Create/prepare one User and bind the existing ERPNext/RetailEdge authorities.

	This method deliberately does not create User Permissions, business-document
	roles, defaults or a parallel POS mapping. Native User, Role, Branch Assignment,
	Branch Setup and ERPNext POS Profile records remain authoritative.
	"""
	_assert_onboarding_read()
	values = _parse_payload(payload)

	# Validate the exact Company -> Branch mapping and any required POS mutation
	# authority before the first onboarding write.
	selected_user = str(values.get("user") or "").strip() if values["mode"] == "existing" else ""
	branch_context = _profile_summary(
		company=values["company"],
		branch=values["branch"],
		user=selected_user,
	)
	if not branch_context.get("configured"):
		frappe.throw(branch_context.get("message") or _("Branch Setup is required before onboarding can continue."))
	if values["requires_pos"]:
		if not branch_context.get("default_pos_profile"):
			frappe.throw(_("Configure a default POS Profile in Branch Setup before assigning POS access."))
		if not branch_context.get("pos_required_supported"):
			frappe.throw(branch_context.get("pos_message") or _("The Branch POS Profile is disabled or belongs to another Company."))
		pos_change_needed = branch_context.get("pos_access_mode") == "restricted" and not (
			branch_context.get("pos_assigned") and branch_context.get("pos_default")
		)
		if pos_change_needed and not branch_context.get("can_manage_pos_profile"):
			frappe.throw(
				_("You do not have permission to update the Branch POS Profile required for this User."),
				frappe.PermissionError,
			)

	user_doc, created_user = _resolve_or_create_user(values)
	role_added = _ensure_retailedge_role(user_doc, values["role"])
	assignment_name, assignment_created = _ensure_branch_assignment(user=user_doc.name, values=values)
	pos = {"access": "not_required", "changed": False}
	if values["requires_pos"]:
		pos = _ensure_pos_access(user=user_doc.name, company=values["company"], branch=values["branch"])

	readiness = get_retailedge_user_readiness(user=user_doc.name, company=values["company"])
	welcome_email_sent = False
	welcome_email_error = ""
	if created_user and values["send_welcome_email"] and readiness.get("ready"):
		try:
			user_doc.send_welcome_mail_to_user()
			welcome_email_sent = True
		except Exception:
			welcome_email_error = _("The User was created, but the welcome email could not be sent.")
			frappe.log_error(frappe.get_traceback(), "RetailEdge User Onboarding Welcome Email")

	return {
		"user": user_doc.name,
		"user_name": user_doc.full_name or user_doc.name,
		"created_user": created_user,
		"role": values["role"],
		"role_added": role_added,
		"branch_assignment": assignment_name,
		"branch_assignment_created": assignment_created,
		"pos": pos,
		"readiness": readiness,
		"welcome_email_sent": welcome_email_sent,
		"welcome_email_error": welcome_email_error,
	}
