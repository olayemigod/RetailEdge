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
_PURCHASE_MANAGER_ROLES = {"Purchase Manager"}
_PURCHASE_USER_ROLES = {"Purchase User"}


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
		key="sales-by-item", label="Sales by Item",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _SALES_MANAGER_ROLES, {"Sales User"}),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _SALES_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _SALES_MANAGER_ROLES), ref_doctype="Sales Invoice",
	),
	"sales-invoice-register": ReportCapabilitySpec(
		key="sales-invoice-register", label="Sales Invoice Register",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _SALES_MANAGER_ROLES, {"Sales User"}),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _SALES_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _SALES_MANAGER_ROLES), ref_doctype="Sales Invoice",
	),
	"customer-receivables": ReportCapabilitySpec(
		key="customer-receivables", label="Customer Receivables",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _SALES_MANAGER_ROLES, {"Sales User"}, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _SALES_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _SALES_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES), ref_doctype="Sales Invoice",
	),
	"purchase-register": ReportCapabilitySpec(
		key="purchase-register", label="Purchase Register",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _PURCHASE_MANAGER_ROLES, _PURCHASE_USER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _PURCHASE_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _PURCHASE_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES), ref_doctype="Purchase Invoice",
	),
	"supplier-payables": ReportCapabilitySpec(
		key="supplier-payables", label="Supplier Payables",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _PURCHASE_MANAGER_ROLES, _PURCHASE_USER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _PURCHASE_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _PURCHASE_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES), ref_doctype="Purchase Invoice",
	),
	"stock-position": ReportCapabilitySpec(
		key="stock-position", label="Stock Position",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _STOCK_MANAGER_ROLES, {"Stock User"}),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _STOCK_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _STOCK_MANAGER_ROLES), ref_doctype="Item",
	),
	"stock-movement-history": ReportCapabilitySpec(
		key="stock-movement-history", label="Stock Movement History",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _STOCK_MANAGER_ROLES, {"Stock User"}),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _STOCK_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _STOCK_MANAGER_ROLES), ref_doctype="Stock Ledger Entry",
	),
	"stock-accounting-integrity": ReportCapabilitySpec(
		key="stock-accounting-integrity", label="Stock & Accounting Integrity",
		view_roles=_roles({"System Manager", "Stock User"}, _STOCK_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		print_roles=_roles({"System Manager"}, _STOCK_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles({"System Manager"}, _STOCK_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES), ref_doctype="Stock Ledger Entry",
	),
	"expense-register": ReportCapabilitySpec(
		key="expense-register", label="Expense Register",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES), ref_doctype="RetailEdge Cashier Expense",
	),
	"expense-review": ReportCapabilitySpec(
		key="expense-review", label="Expense Review",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES), ref_doctype="RetailEdge Cashier Expense",
	),
	"cash-shift-verification": ReportCapabilitySpec(
		key="cash-shift-verification", label="Cash Shift Verification",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES), ref_doctype="RetailEdge Daily Sales Audit",
	),
	"daily-sales-audit": ReportCapabilitySpec(
		key="daily-sales-audit", label="Daily Sales Audit",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES), ref_doctype="RetailEdge Daily Sales Audit",
	),
	"cash-movement": ReportCapabilitySpec(
		key="cash-movement", label="Cash Movement",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES), ref_doctype="Payment Entry",
	),
	"cash-flow-outlook": ReportCapabilitySpec(
		key="cash-flow-outlook", label="Cash Flow Outlook",
		view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES),
		print_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
		export_roles=_roles(_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES),
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


def _has_ref_read_permission(spec: ReportCapabilitySpec, user: str) -> bool:
	if not spec.ref_doctype or not frappe.db.exists("DocType", spec.ref_doctype):
		return True
	return bool(frappe.has_permission(spec.ref_doctype, ptype="read", user=user))


def get_report_capabilities(report_key: str, company: str = "", branch: str = "", user: str | None = None) -> dict[str, object]:
	user = user or frappe.session.user
	spec = get_report_capability_spec(report_key)
	_validate_scope(company=company, branch=branch, user=user)
	roles = _user_roles(user)
	can_view = bool(roles.intersection(spec.view_roles)) and _has_ref_read_permission(spec, user)
	print_setting = _setting_enabled(PRINT_SETTING, default=True)
	export_setting = _setting_enabled(EXPORT_SETTING, default=True)
	can_print = can_view and print_setting and bool(roles.intersection(spec.print_roles))
	can_export = can_view and export_setting and bool(roles.intersection(spec.export_roles))
	return {
		"scope_name": spec.label, "scope_key": spec.key, "scope_type": "report",
		"can_view": can_view, "can_print": can_print, "can_export": can_export,
		"authorization_model": "settings_scope_role_document_and_branch_permission",
	}


def require_report_action(report_key: str, action: str = "view", company: str = "", branch: str = "", user: str | None = None) -> dict[str, object]:
	capabilities = get_report_capabilities(report_key, company=company, branch=branch, user=user)
	action = cstr(action or "view").strip().lower()
	allowed = {"view": capabilities["can_view"], "print": capabilities["can_print"], "export": capabilities["can_export"]}.get(action)
	if allowed:
		return capabilities
	if action not in {"view", "print", "export"}:
		frappe.throw(_("Unsupported RetailEdge reporting action."))
	frappe.throw(_("You are not permitted to {0} this report, or the capability is disabled in RetailEdge Settings.").format(action), frappe.PermissionError)


@frappe.whitelist()
def get_shell_capabilities(report_key: str, company: str = "", branch: str = "") -> dict[str, object]:
	return get_report_capabilities(report_key, company=company, branch=branch)
