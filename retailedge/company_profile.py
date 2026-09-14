from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.operating_context import (
	get_allowed_operating_branches,
	get_allowed_operating_contexts,
	get_operating_context,
)


def _clean(value: Any) -> str:
	return str(value or "").strip()


def resolve_company_profile(company: str) -> dict[str, Any]:
	"""Return presentation-safe ERPNext Company identity without duplicating Company truth."""
	company = _clean(company)
	fallback = {
		"name": company,
		"label": company,
		"logo": "",
		"abbr": "",
		"currency": "",
		"country": "",
		"tax_id": "",
		"website": "",
	}
	if not company or not frappe.db.exists("Company", company):
		return fallback

	meta = frappe.get_meta("Company")
	fields = ["name"]
	for fieldname in (
		"company_name",
		"company_logo",
		"abbr",
		"default_currency",
		"country",
		"tax_id",
		"website",
	):
		if meta.has_field(fieldname):
			fields.append(fieldname)
	row = frappe.db.get_value("Company", company, fields, as_dict=True) or {}
	return {
		"name": row.get("name") or company,
		"label": row.get("company_name") or row.get("name") or company,
		"logo": row.get("company_logo") or "",
		"abbr": row.get("abbr") or "",
		"currency": row.get("default_currency") or "",
		"country": row.get("country") or "",
		"tax_id": row.get("tax_id") or "",
		"website": row.get("website") or "",
	}


def _assert_company_access(company: str) -> None:
	if not company:
		frappe.throw(_("Company is required."))
	# Operating Context is the RetailEdge product authority. This validation also
	# preserves assignment-authoritative users who may not have generic Company read.
	get_allowed_operating_contexts(company=company)


@frappe.whitelist()
def get_company_profile(company: str = "") -> dict[str, Any]:
	current = get_operating_context()
	company = _clean(company) or _clean(current.get("company"))
	_assert_company_access(company)
	profile = resolve_company_profile(company)
	try:
		can_write = bool(frappe.has_permission("Company", "write", doc=company))
	except Exception:
		can_write = False
	return {
		"profile": profile,
		"operating_context": current,
		"can_write": can_write,
		"source_of_truth": "ERPNext Company",
	}


@frappe.whitelist()
def get_shell_identity() -> dict[str, Any]:
	current = get_operating_context()
	company = _clean(current.get("company"))
	profile = resolve_company_profile(company)
	branches = get_allowed_operating_branches(company=company) if company else []
	return {
		"product_code": "retailedge",
		"product_name": "RetailEdge",
		"product_logo": "",
		"product_icon": "shopping-cart",
		"product_subtitle": "Retail operations & control",
		"tenant_name": profile.get("label") or company,
		"tenant_logo": profile.get("logo") or "",
		"tenant_icon": "building",
		"tenant_subtitle": "Business workspace",
		"active_company": company,
		"active_branch": _clean(current.get("branch")),
		"branch_options": list(branches),
		"can_switch_branch": len(branches) > 1,
		"company_profile": profile,
	}
