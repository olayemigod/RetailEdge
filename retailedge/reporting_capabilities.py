from __future__ import annotations

from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import cint, cstr

from retailedge.branch_context import validate_user_branch_access
from retailedge.utils.settings import RETAILEDGE_SETTINGS_DOCTYPE

PRINT_SETTING = "enable_reporting_print"
EXPORT_SETTING = "enable_reporting_export"

_MANAGER_ROLES = {
	"System Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}
_BRANCH_MANAGER_ROLES = {"RetailEdge Branch Manager", "RetailEdgeBranchManager"}
_SALES_MANAGER_ROLES = {"Sales Manager"}
_STOCK_MANAGER_ROLES = {"Stock Manager"}
_ACCOUNTS_MANAGER_ROLES = {"Accounts Manager"}
_ACCOUNTS_USER_ROLES = {"Accounts User"}


@dataclass(frozen=True)
class ReportCapabilitySpec:
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


_REPORT_SPECS = {
	"sales-by-item": ReportCapabilitySpec(
		key="sales-by-item",
		label="Sales by Item",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _SALES_MANAGER_ROLES, {"Sales User"}),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _SALES_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _SALES_MANAGER_ROLES),
		ref_doctype="Sales Invoice",
	),
	"sales-invoice-register": ReportCapabilitySpec(
		key="sales-invoice-register",
		label="Sales Invoice Register",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _SALES_MANAGER_ROLES, {"Sales User"}),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _SALES_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _SALES_MANAGER_ROLES),
		ref_doctype="Sales Invoice",
	),
	"stock-position": ReportCapabilitySpec(
		key="stock-position",
		label="Stock Position",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _STOCK_MANAGER_ROLES, {"Stock User"}),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _STOCK_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _STOCK_MANAGER_ROLES),
		ref_doctype="Item",
	),
	"stock-movement-history": ReportCapabilitySpec(
		key="stock-movement-history",
		label="Stock Movement History",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _STOCK_MANAGER_ROLES, {"Stock User"}),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _STOCK_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _STOCK_MANAGER_ROLES),
		ref_doctype="Stock Ledger Entry",
	),
	"expense-register": ReportCapabilitySpec(
		key="expense-register",
		label="Expense Register",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		ref_doctype="RetailEdge Cashier Expense",
	),
	"cash-movement": ReportCapabilitySpec(
		key="cash-movement",
		label="Cash Movement",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		ref_doctype="Payment Entry",
	),
}


def get_report_capability_spec(report_key: str) -> ReportCapabilitySpec:
	key = cstr(report_key or "").strip().lower()
	spec = _REPORT_SPECS.get(key)
	if not spec:
		frappe.throw(_("Unsupported RetailEdge report capability scope."))
	return spec


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


def _validate_scope(*, company: str = "", branch: str = "", user: str) -> None:
	company = cstr(company or "").strip()
	branch = cstr(branch or "").strip()
	if company and not frappe.has_permission("Company", "read", doc=company, user=user):
		frappe.throw(_("You do not have access to this Company."), frappe.PermissionError)
	if branch:
		validate_user_branch_access(branch, user=user, company=company or None, throw=True)


def _has_ref_read_permission(spec: ReportCapabilitySpec, user: str) -> bool:
	if not spec.ref_doctype or not frappe.db.exists("DocType", spec.ref_doctype):
		return True
	return bool(frappe.has_permission(spec.ref_doctype, ptype="read", user=user))


def get_report_capabilities(
	report_key: str,
	company: str = "",
	branch: str = "",
	user: str | None = None,
) -> dict[str, object]:
	user = user or frappe.session.user
	spec = get_report_capability_spec(report_key)
	_validate_scope(company=company, branch=branch, user=user)
	roles = _user_roles(user)
	role_can_view = bool(roles.intersection(spec.view_roles))
	can_view = role_can_view and _has_ref_read_permission(spec, user)
	print_setting = _setting_enabled(PRINT_SETTING, default=True)
	export_setting = _setting_enabled(EXPORT_SETTING, default=True)
	can_print = can_view and print_setting and bool(roles.intersection(spec.print_roles))
	can_export = can_view and export_setting and bool(roles.intersection(spec.export_roles))
	return {
		"scope_name": spec.label,
		"scope_key": spec.key,
		"scope_type": "report",
		"can_view": can_view,
		"can_print": can_print,
		"can_export": can_export,
		"authorization_model": "settings_scope_role_and_document_permission",
	}


def require_report_action(
	report_key: str,
	action: str = "view",
	company: str = "",
	branch: str = "",
	user: str | None = None,
) -> dict[str, object]:
	capabilities = get_report_capabilities(
		report_key,
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
		frappe.throw(_("Unsupported RetailEdge reporting action."))
	frappe.throw(
		_("You are not permitted to {0} this report, or the capability is disabled in RetailEdge Settings.").format(action),
		frappe.PermissionError,
	)


@frappe.whitelist()
def get_shell_capabilities(report_key: str, company: str = "", branch: str = "") -> dict[str, object]:
	return get_report_capabilities(report_key, company=company, branch=branch)
