from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cstr

from retailedge.branch_context import resolve_branch_from_pos_profile
from retailedge.branch_performance import _coerce_filters, assert_can_access_branch_performance
from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.operating_context import get_operational_branch_scope, validate_operating_branch
from retailedge.reporting.date_ranges import get_preset_dates
from retailedge.retailedge.report.retailedge_branch_performance_summary.retailedge_branch_performance_summary import (
	execute as execute_branch_performance_report,
)

DASHBOARD_KEY = "branch-performance"
BRANCH_SETUP_DOCTYPE = "RetailEdge Branch Profile"
MAX_LINK_RESULTS = 20
MAX_POS_PROFILE_SCAN = 60
MAX_BRANCH_SETUP_SCAN = 100


def _default_company() -> str:
	return cstr(
		frappe.defaults.get_user_default("Company")
		or frappe.defaults.get_global_default("company")
		or ""
	)


def _filters(value=None) -> frappe._dict:
	filters = _coerce_filters(value or {})
	if not filters.get("company"):
		filters.company = _default_company()
	return filters


def _assert_company(company: str) -> None:
	if company and not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have access to this Company."), frappe.PermissionError)


def _format_summary(summary: list[dict]) -> list[dict]:
	tones = {"Red": "danger", "Orange": "warning", "Green": "success", "Blue": "info"}
	return [{**card, "tone": tones.get(card.get("indicator"), "neutral")} for card in summary]


@frappe.whitelist()
def get_branch_performance_dashboard_context() -> dict:
	assert_can_access_branch_performance()
	company = _default_company()
	from_date, to_date = get_preset_dates("This Month")
	capabilities = require_dashboard_action(DASHBOARD_KEY, "view", company=company)
	return {
		"dashboard_key": DASHBOARD_KEY,
		"default_filters": {
			"company": company,
			"branch": "",
			"pos_profile": "",
			"cashier": "",
			"date_range_preset": "This Month",
			"from_date": str(from_date or ""),
			"to_date": str(to_date or ""),
			"payment_method": "",
			"only_pos_invoices": 0,
			"include_unattributed": 1,
			"include_fallback_branch_resolution": 0,
		},
		"payment_methods": ["Cash", "Bank Transfer", "Card / POS", "Mobile Money", "Other"],
		"capabilities": capabilities,
		"user_name": frappe.get_cached_value("User", frappe.session.user, "full_name")
		or frappe.session.user,
		"tenant_name": company,
	}


@frappe.whitelist()
def get_branch_performance_dashboard_data(filters=None) -> dict:
	assert_can_access_branch_performance()
	filters = _filters(filters)
	_assert_company(filters.get("company"))
	require_dashboard_action(
		DASHBOARD_KEY,
		"view",
		company=filters.get("company"),
		branch=filters.get("branch"),
	)
	columns, rows, message, _chart, summary = execute_branch_performance_report(filters)
	messages = []
	if message:
		messages.append(message)
	for row in rows:
		for row_message in row.get("messages") or []:
			if row_message and row_message not in messages:
				messages.append(row_message)
	return {
		"title": _("Branch Performance"),
		"columns": columns,
		"rows": rows,
		"summary": _format_summary(summary),
		"messages": messages,
		"filters": dict(filters),
		"metadata": {
			"source": "RetailEdge Branch Performance Summary",
			"detail_report": "RetailEdge Branch Performance Summary",
			"accounting_truth": "Submitted ERPNext sales and posted RetailEdge control records",
		},
	}


def _search_companies(like: str) -> list[dict]:
	rows = frappe.get_list(
		"Company",
		filters={"name": ["like", like]},
		fields=["name"],
		order_by="name asc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	return [{"value": row.name, "label": row.name} for row in rows]


def _search_branches(like: str, company: str) -> list[dict]:
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	allowed = list(scope.get("allowed_branches") or [])
	if scope.get("restricted") and not allowed:
		return []
	filters: list[list] = [["Branch", "name", "like", like]]
	if scope.get("restricted"):
		filters.append(["Branch", "name", "in", allowed])
	if company and frappe.get_meta("Branch").has_field("company"):
		filters.append(["Branch", "company", "=", company])
	rows = frappe.get_list(
		"Branch",
		filters=filters,
		fields=["name"],
		order_by="name asc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	return [{"value": row.name, "label": row.name} for row in rows]


def _resolve_option_branch_scope(company: str, branch: str = "") -> dict:
	user = frappe.session.user
	branch = cstr(branch).strip()
	scope = get_operational_branch_scope(company, user=user)
	allowed = [
		cstr(value).strip()
		for value in dict.fromkeys(scope.get("allowed_branches") or [])
		if cstr(value).strip()
	]
	restricted = bool(scope.get("restricted"))
	if restricted and not allowed:
		return {"restricted": True, "branches": []}
	if branch:
		if restricted and branch not in allowed:
			frappe.throw(
				_("You do not have active RetailEdge Branch access to Branch {0}.").format(branch),
				frappe.PermissionError,
			)
		validate_operating_branch(company=company, branch=branch, user=user, throw=True)
		return {"restricted": restricted, "branches": [branch]}
	return {"restricted": restricted, "branches": allowed if restricted else []}


def _branch_setup_rows(company: str, branches: list[str]) -> list:
	if not frappe.db.exists("DocType", BRANCH_SETUP_DOCTYPE):
		return []
	if not frappe.has_permission(BRANCH_SETUP_DOCTYPE, "read"):
		return []
	filters = {"company": company, "enabled": 1}
	if branches:
		filters["branch"] = ["in", branches]
	return frappe.get_list(
		BRANCH_SETUP_DOCTYPE,
		filters=filters,
		fields=["name", "branch", "default_pos_profile"],
		order_by="branch asc, modified desc",
		limit_page_length=MAX_BRANCH_SETUP_SCAN,
	)


def _scoped_pos_profile_names(
	company: str,
	branch_scope: dict,
	*,
	like: str = "%%",
) -> list[str]:
	if not frappe.db.exists("DocType", "POS Profile"):
		return []
	if branch_scope.get("restricted") and not branch_scope.get("branches"):
		return []

	meta = frappe.get_meta("POS Profile")
	filters = {"name": ["like", like]}
	if company and meta.has_field("company"):
		filters["company"] = company
	if meta.has_field("disabled"):
		filters["disabled"] = 0
	candidates = frappe.get_list(
		"POS Profile",
		filters=filters,
		fields=["name"],
		order_by="name asc",
		limit_page_length=MAX_POS_PROFILE_SCAN,
	)
	branches = set(branch_scope.get("branches") or [])
	if not branches and not branch_scope.get("restricted"):
		return [row.name for row in candidates]

	setup_rows = _branch_setup_rows(company, list(branches))
	configured = {
		cstr(row.get("default_pos_profile")).strip()
		for row in setup_rows
		if cstr(row.get("default_pos_profile")).strip()
	}
	result = []
	for row in candidates:
		name = cstr(row.name).strip()
		if name in configured:
			result.append(name)
			continue
		resolved = resolve_branch_from_pos_profile(name, company=company)
		if cstr(resolved.get("branch")).strip() in branches:
			result.append(name)
	return result


def _search_pos_profiles(like: str, company: str, branch_scope: dict) -> list[dict]:
	names = _scoped_pos_profile_names(company, branch_scope, like=like)
	return [{"value": name, "label": name} for name in names[:MAX_LINK_RESULTS]]


def _branch_cashier_users(setup_rows: list) -> set[str]:
	users: set[str] = set()
	for row in setup_rows:
		name = cstr(row.get("name")).strip()
		if not name or not frappe.has_permission(BRANCH_SETUP_DOCTYPE, "read", doc=name):
			continue
		doc = frappe.get_doc(BRANCH_SETUP_DOCTYPE, name)
		for member in getattr(doc, "default_cashiers", []) or []:
			user = cstr(getattr(member, "user", None) or member.get("user")).strip()
			if user:
				users.add(user)
	return users


def _pos_profile_users(profile_names: list[str]) -> set[str]:
	users: set[str] = set()
	for name in profile_names[:MAX_POS_PROFILE_SCAN]:
		if not frappe.has_permission("POS Profile", "read", doc=name):
			continue
		doc = frappe.get_doc("POS Profile", name)
		for field in doc.meta.get_table_fields():
			if field.options != "POS Profile User":
				continue
			for member in doc.get(field.fieldname) or []:
				user = cstr(getattr(member, "user", None) or member.get("user")).strip()
				if user:
					users.add(user)
	return users


def _search_cashiers(
	like: str,
	company: str,
	branch_scope: dict,
	pos_profile: str = "",
) -> list[dict]:
	if branch_scope.get("restricted") and not branch_scope.get("branches"):
		return []
	setup_rows = _branch_setup_rows(company, list(branch_scope.get("branches") or []))
	profile_names = _scoped_pos_profile_names(company, branch_scope)
	selected_profile = cstr(pos_profile).strip()
	if selected_profile:
		if selected_profile not in profile_names:
			return []
		profile_names = [selected_profile]

	users = _branch_cashier_users(setup_rows)
	users.update(_pos_profile_users(profile_names))
	if not users:
		return []
	rows = frappe.get_list(
		"User",
		filters={"enabled": 1, "name": ["in", sorted(users)]},
		or_filters={"name": ["like", like], "full_name": ["like", like]},
		fields=["name", "full_name"],
		order_by="full_name asc, name asc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	return [
		{"value": row.name, "label": row.full_name or row.name, "description": row.name}
		for row in rows
	]


@frappe.whitelist()
def search_branch_performance_options(
	kind: str,
	txt: str = "",
	company: str = "",
	branch: str = "",
	pos_profile: str = "",
) -> list[dict]:
	assert_can_access_branch_performance()
	kind = cstr(kind).strip().lower()
	company = cstr(company or _default_company()).strip()
	branch = cstr(branch).strip()
	pos_profile = cstr(pos_profile).strip()
	like = f"%{cstr(txt).strip()}%"
	if kind == "company":
		return _search_companies(like)
	_assert_company(company)
	if kind == "branch":
		return _search_branches(like, company)
	branch_scope = _resolve_option_branch_scope(company, branch)
	if kind == "pos_profile":
		return _search_pos_profiles(like, company, branch_scope)
	if kind == "cashier":
		return _search_cashiers(like, company, branch_scope, pos_profile=pos_profile)
	frappe.throw(_("Unsupported Branch Performance search type."))
