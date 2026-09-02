from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.branch_assignment import has_branch_assignments
from retailedge.branch_context import get_user_allowed_branches, user_has_global_branch_access
from retailedge.branch_profile import get_enabled_branch_profiles, get_user_branch_profiles
from retailedge.operating_context import get_allowed_operating_branches, validate_operating_branch


def get_report_branch_scope(company: str, *, user: str | None = None) -> dict[str, Any]:
	"""Return the authoritative reporting Branch scope for one Company.

	Branch Assignment is authoritative once assignment history exists. Legacy
	User Permission/default/Profile restrictions remain fallback for users not yet
	migrated to Branch Assignment. A user with no configured Branch restriction is
	not made restricted merely because they do not hold a global-branch role.
	"""
	user = user or frappe.session.user
	company = str(company or "").strip()
	if not company or user_has_global_branch_access(user=user):
		return {
			"company": company,
			"restricted": False,
			"allowed_branches": [],
			"source": "global" if company else "no_company",
		}

	has_assignments = has_branch_assignments(user=user)
	legacy = list(get_user_allowed_branches(user=user, company=company).get("branches") or [])
	profile_rows = get_user_branch_profiles(user=user, company=company)
	profile_branches = [
		str(row.get("branch") or "").strip()
		for row in profile_rows
		if row.get("enabled") and str(row.get("branch") or "").strip()
	]
	restricted = bool(has_assignments or legacy or profile_branches)
	if not restricted:
		return {
			"company": company,
			"restricted": False,
			"allowed_branches": [],
			"source": "unrestricted_legacy",
		}

	allowed = list(dict.fromkeys(get_allowed_operating_branches(company=company, user=user)))
	if not allowed:
		frappe.throw(
			_("Your Branch reporting access is not active for Company {0}.").format(company),
			frappe.PermissionError,
		)
	return {
		"company": company,
		"restricted": True,
		"allowed_branches": allowed,
		"source": "branch_assignment" if has_assignments else "legacy_branch_restriction",
	}


def validate_report_scope(
	*,
	company: str = "",
	branch: str = "",
	user: str | None = None,
	require_branch_when_restricted: bool = True,
) -> dict[str, Any]:
	"""Validate Company/Branch report scope without trusting client filters."""
	user = user or frappe.session.user
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	if not company:
		return {
			"company": "",
			"branch": branch,
			"restricted": False,
			"allowed_branches": [],
			"source": "no_company",
		}
	if not frappe.has_permission("Company", "read", doc=company, user=user):
		frappe.throw(_("You do not have access to this Company."), frappe.PermissionError)

	scope = get_report_branch_scope(company, user=user)
	if branch:
		validate_operating_branch(company=company, branch=branch, user=user, throw=True)
		if scope["restricted"] and branch not in scope["allowed_branches"]:
			frappe.throw(_("You do not have reporting access to Branch {0}.").format(branch), frappe.PermissionError)
	elif scope["restricted"] and require_branch_when_restricted:
		frappe.throw(
			_("Choose one of your assigned Branches. Cross-branch reporting is available only to authorized managers."),
			frappe.PermissionError,
		)
	return {**scope, "branch": branch}


def constrain_report_filters(
	filters: dict[str, Any] | frappe._dict | None,
	*,
	user: str | None = None,
	require_branch_when_restricted: bool = True,
) -> dict[str, Any]:
	"""Return a copied filter set after authoritative report-scope validation."""
	resolved = dict(filters or {})
	company = str(resolved.get("company") or "").strip()
	branch = str(resolved.get("branch") or "").strip()
	validated = validate_report_scope(
		company=company,
		branch=branch,
		user=user,
		require_branch_when_restricted=require_branch_when_restricted,
	)
	if company:
		resolved["company"] = company
	if branch:
		resolved["branch"] = validated["branch"]
	return resolved


def assert_company_wide_report_scope(company: str, *, user: str | None = None) -> None:
	"""Allow Company-wide data only when Branch restrictions cannot hide another Branch."""
	user = user or frappe.session.user
	company = str(company or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	if not frappe.has_permission("Company", "read", doc=company, user=user):
		frappe.throw(_("You do not have access to this Company."), frappe.PermissionError)
	if user_has_global_branch_access(user=user):
		return

	scope = get_report_branch_scope(company, user=user)
	if not scope["restricted"]:
		return

	company_branches = _configured_company_branches(company)
	if len(company_branches) == 1 and company_branches[0] in scope["allowed_branches"]:
		return
	frappe.throw(
		_(
			"This is a Company-wide control. Your current Branch access cannot safely review all Company data."
		),
		frappe.PermissionError,
	)


def _configured_company_branches(company: str) -> list[str]:
	"""Return a Company Branch universe only when RetailEdge/ERPNext can prove it."""
	profiles = get_enabled_branch_profiles(company=company)
	profile_branches = list(
		dict.fromkeys(
			str(row.get("branch") or "").strip()
			for row in profiles
			if str(row.get("branch") or "").strip()
		)
	)
	if profile_branches:
		return profile_branches

	if not frappe.db.exists("DocType", "Branch"):
		return []
	meta = frappe.get_meta("Branch")
	if not meta.has_field("company"):
		# ERPNext v16 has no native Branch.company. Without Branch Setup there is
		# no safe Company→Branch universe to prove Company-wide equivalence.
		return []
	filters: dict[str, Any] = {"company": company}
	if meta.has_field("disabled"):
		filters["disabled"] = 0
	rows = frappe.get_all(
		"Branch",
		filters=filters,
		pluck="name",
		limit_page_length=500,
	)
	return list(dict.fromkeys(str(branch).strip() for branch in rows if str(branch).strip()))
