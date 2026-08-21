from __future__ import annotations

from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import cint, cstr

from retailedge.branch_context import (
	get_user_allowed_branches,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.reporting_capabilities import EXPORT_SETTING, PRINT_SETTING
from retailedge.utils.settings import RETAILEDGE_SETTINGS_DOCTYPE

_MANAGER_ROLES = {
	"System Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}
_BRANCH_MANAGER_ROLES = {"RetailEdge Branch Manager", "RetailEdgeBranchManager"}
_ACCOUNTS_MANAGER_ROLES = {"Accounts Manager"}
_ACCOUNTS_USER_ROLES = {"Accounts User"}


@dataclass(frozen=True)
class DashboardCapabilitySpec:
	key: str
	label: str
	view_roles: frozenset[str]
	print_roles: frozenset[str]
	export_roles: frozenset[str]
	ref_doctype: str = ""


def _roles(*groups: set[str]) -> frozenset[str]:
	combined: set[str] = set()
	for group in groups:
		combined.update(group)
	return frozenset(combined)


_DASHBOARD_SPECS = {
	"owner-dashboard": DashboardCapabilitySpec(
		key="owner-dashboard",
		label="Owner Dashboard",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		ref_doctype="Company",
	),
	"profitability-intelligence": DashboardCapabilitySpec(
		key="profitability-intelligence",
		label="Profitability Intelligence",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		ref_doctype="Sales Invoice",
	),
	"sales-overview": DashboardCapabilitySpec(
		key="sales-overview",
		label="Sales Overview",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		ref_doctype="Sales Invoice",
	),
	"money-overview": DashboardCapabilitySpec(
		key="money-overview",
		label="Money Overview",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		ref_doctype="Account",
	),
	"expense-overview": DashboardCapabilitySpec(
		key="expense-overview",
		label="Expenses Dashboard",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		ref_doctype="RetailEdge Cashier Expense",
	),
	"branch-performance": DashboardCapabilitySpec(
		key="branch-performance",
		label="Branch Performance",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		ref_doctype="Branch",
	),
	"salesperson-performance": DashboardCapabilitySpec(
		key="salesperson-performance",
		label="Salesperson Performance",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		ref_doctype="Sales Invoice",
	),
}


def _setting_enabled(fieldname: str, default: bool = True) -> bool:
	if not frappe.db.exists("DocType", RETAILEDGE_SETTINGS_DOCTYPE):
		return default
	meta = frappe.get_meta(RETAILEDGE_SETTINGS_DOCTYPE)
	if not meta.has_field(fieldname):
		return default
	value = frappe.db.get_single_value(RETAILEDGE_SETTINGS_DOCTYPE, fieldname)
	if value in (None, ""):
		return default
	return bool(cint(value))


def _user_roles(user: str) -> set[str]:
	if user == "Administrator":
		return {"System Manager"}
	if user == "Guest":
		return set()
	return set(frappe.get_roles(user))


def _spec(scope_key: str) -> DashboardCapabilitySpec:
	key = cstr(scope_key or "").strip().lower()
	spec = _DASHBOARD_SPECS.get(key)
	if not spec:
		frappe.throw(_("Unsupported RetailEdge dashboard capability scope."))
	return spec


def _company_branch_count(company: str) -> int:
	if not company or not frappe.db.exists("DocType", "Branch"):
		return 0
	meta = frappe.get_meta("Branch")
	if not meta.has_field("company"):
		return 0
	return int(frappe.db.count("Branch", filters={"company": company}) or 0)


def _validate_scope(*, company: str = "", branch: str = "", user: str) -> None:
	company = cstr(company or "").strip()
	branch = cstr(branch or "").strip()
	if company and not frappe.has_permission("Company", "read", doc=company, user=user):
		frappe.throw(_("You do not have access to this Company."), frappe.PermissionError)
	if branch:
		validate_user_branch_access(branch, user=user, company=company or None, throw=True)
		return
	if not company or user_has_global_branch_access(user=user):
		return
	if _company_branch_count(company) <= 1:
		return
	allowed = list(get_user_allowed_branches(user=user, company=company).get("branches") or [])
	if not allowed:
		frappe.throw(
			_("Your Branch access is not configured for this multi-branch Company."),
			frappe.PermissionError,
		)


def get_dashboard_capabilities(
	scope_key: str,
	company: str = "",
	branch: str = "",
	user: str | None = None,
) -> dict[str, object]:
	user = user or frappe.session.user
	spec = _spec(scope_key)
	_validate_scope(company=company, branch=branch, user=user)
	roles = _user_roles(user)
	can_view = bool(roles.intersection(spec.view_roles))
	if can_view and spec.ref_doctype and frappe.db.exists("DocType", spec.ref_doctype):
		can_view = bool(frappe.has_permission(spec.ref_doctype, ptype="read", user=user))
	can_print = can_view and _setting_enabled(PRINT_SETTING) and bool(roles.intersection(spec.print_roles))
	can_export = can_view and _setting_enabled(EXPORT_SETTING) and bool(roles.intersection(spec.export_roles))
	return {
		"scope_name": spec.label,
		"scope_key": spec.key,
		"scope_type": "dashboard",
		"can_view": can_view,
		"can_print": can_print,
		"can_export": can_export,
		"authorization_model": "settings_scope_role_document_and_branch_permission",
	}


def require_dashboard_action(
	scope_key: str,
	action: str = "view",
	company: str = "",
	branch: str = "",
	user: str | None = None,
) -> dict[str, object]:
	capabilities = get_dashboard_capabilities(
		scope_key,
		company=company,
		branch=branch,
		user=user,
	)
	action = cstr(action or "view").strip().lower()
	allowed = {
		"view": capabilities["can_view"],
		"print": capabilities["can_print"],
		"export": capabilities["can_export"],
	}.get(action)
	if allowed:
		return capabilities
	if action not in {"view", "print", "export"}:
		frappe.throw(_("Unsupported RetailEdge dashboard action."))
	frappe.throw(
		_("You are not permitted to {0} this dashboard, or the capability is disabled in RetailEdge Settings.").format(action),
		frappe.PermissionError,
	)


@frappe.whitelist()
def get_dashboard_shell_capabilities(scope_key: str, company: str = "", branch: str = "") -> dict[str, object]:
	return get_dashboard_capabilities(scope_key, company=company, branch=branch)
