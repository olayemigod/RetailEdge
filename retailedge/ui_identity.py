from __future__ import annotations

import frappe

from retailedge.branch_context import (
	get_user_allowed_branches,
	has_doctype,
	has_field,
	resolve_branch_from_user,
	user_has_global_branch_access,
)


PRODUCT_KEY = "retailedge"


def _default_company(user: str) -> str:
	try:
		return (
			frappe.defaults.get_user_default("Company", user=user)
			or frappe.defaults.get_user_default("Company")
			or frappe.defaults.get_global_default("company")
			or ""
		)
	except Exception:
		return ""


def _company_identity(company: str) -> dict:
	if not company:
		return {"name": "", "label": "", "logo": ""}
	try:
		row = frappe.db.get_value(
			"Company",
			company,
			["name", "company_name", "company_logo"],
			as_dict=True,
		) or {}
	except Exception:
		row = {}
	return {
		"name": row.get("name") or company,
		"label": row.get("company_name") or company,
		"logo": row.get("company_logo") or "",
	}


def _user_identity(user: str) -> dict:
	try:
		row = frappe.db.get_value(
			"User",
			user,
			["name", "full_name", "user_image"],
			as_dict=True,
		) or {}
	except Exception:
		row = {}
	return {
		"email": row.get("name") or user,
		"full_name": row.get("full_name") or user,
		"image": row.get("user_image") or "",
	}


def get_retailedge_branch_options(user: str | None = None, company: str | None = None) -> list[dict]:
	user = user or frappe.session.user
	company = company or _default_company(user)
	if not has_doctype("Branch"):
		return []

	branches: list[str] = []
	if user_has_global_branch_access(user=user):
		filters = {}
		if company and has_field("Branch", "company"):
			filters["company"] = company
		try:
			branches = frappe.get_all(
				"Branch",
				filters=filters,
				pluck="name",
				order_by="name asc",
				limit_page_length=200,
			) or []
		except Exception:
			branches = []
	else:
		branches = list((get_user_allowed_branches(user=user, company=company) or {}).get("branches") or [])

	rows_by_name: dict[str, dict] = {}
	if branches:
		fields = ["name"]
		if has_field("Branch", "company"):
			fields.append("company")
		try:
			rows = frappe.get_all(
				"Branch",
				filters={"name": ["in", branches]},
				fields=fields,
				limit_page_length=200,
			)
			rows_by_name = {row.get("name"): row for row in rows if row.get("name")}
		except Exception:
			rows_by_name = {}

	options = []
	for branch in dict.fromkeys(branches):
		row = rows_by_name.get(branch, {})
		options.append(
			{
				"value": branch,
				"label": branch,
				"company": row.get("company") or company or "",
				"code": "",
			}
		)
	return options


def get_retailedge_ui_identity(user: str | None = None) -> dict:
	user = user or frappe.session.user
	company = _default_company(user)
	company_identity = _company_identity(company)
	user_identity = _user_identity(user)
	branch_context = resolve_branch_from_user(user=user, company=company)
	branch = branch_context.get("branch") or ""
	branches = get_retailedge_branch_options(user=user, company=company)

	if branch and branch not in {option["value"] for option in branches}:
		branches.insert(
			0,
			{
				"value": branch,
				"label": branch,
				"company": company,
				"code": "",
			},
		)

	companies = {}
	if company_identity["name"]:
		companies[company_identity["name"]] = {
			"label": company_identity["label"],
			"logo": company_identity["logo"],
		}

	return {
		"product_key": PRODUCT_KEY,
		"product_name": "RetailEdge",
		"product_subtitle": "Retail operations and business intelligence",
		"product_icon": "chart",
		"tenant_name": company_identity["label"] or company or "Retail Business",
		"tenant_subtitle": "Retail operations workspace",
		"tenant_logo": company_identity["logo"],
		"tenant_icon": "building",
		"companies": companies,
		"company": company,
		"branch": branch,
		"branch_source": branch_context.get("source") or "",
		"branches": branches,
		"can_switch_branch": len(branches) > 1,
		"user": user_identity,
	}


def extend_bootinfo(bootinfo) -> dict:
	identity = get_retailedge_ui_identity()

	shared_identity = getattr(bootinfo, "edgesuite_ui_identity", None)
	if not isinstance(shared_identity, dict):
		shared_identity = {}
	shared_identity[PRODUCT_KEY] = {
		key: identity[key]
		for key in (
			"product_name",
			"product_subtitle",
			"product_icon",
			"tenant_name",
			"tenant_subtitle",
			"tenant_logo",
			"tenant_icon",
			"companies",
		)
	}
	bootinfo.edgesuite_ui_identity = shared_identity

	product_menu = getattr(bootinfo, "edgesuite_product_menu", None)
	if not isinstance(product_menu, dict):
		product_menu = {}
	product_menu.update(
		{
			"product": "RetailEdge",
			"company": identity.get("company") or "",
			"branch": identity.get("branch") or "",
		}
	)
	bootinfo.edgesuite_product_menu = product_menu
	return identity
