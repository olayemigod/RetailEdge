from __future__ import annotations

import frappe
from frappe.desk.search import validate_and_sanitize_search_inputs
from frappe.utils import cint


MAX_BRANCH_RESULTS = 20


@frappe.whitelist()
@validate_and_sanitize_search_inputs
def search_available_branch_setup_branches(doctype, txt, searchfield, start, page_len, filters):
	"""Return Branch masters that are still available for one RetailEdge Branch Setup.

	ERPNext v16 Branch is intentionally global and has no native Company field.
	RetailEdge Branch Setup therefore owns the Company↔Branch binding.  The UI
	must not pretend Branch has a Company column; instead it requires Company
	first and hides Branches already reserved by another enabled Branch Setup.
	Backend validation in ``branch_profile.validate_branch_profile`` remains the
	authoritative guard against duplicate or cross-company bindings.
	"""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	company = str(filters.get("company") or "").strip()
	if not company:
		return []

	profile_name = str(filters.get("profile_name") or "").strip()
	reserved = _reserved_enabled_branches(profile_name=profile_name)
	branch_filters = []
	if txt:
		branch_filters.append(["Branch", "name", "like", f"%{txt}%"])
	if reserved:
		branch_filters.append(["Branch", "name", "not in", reserved])

	rows = frappe.get_list(
		"Branch",
		filters=branch_filters,
		fields=["name"],
		order_by="name asc",
		limit_start=max(cint(start), 0),
		limit_page_length=min(cint(page_len) or MAX_BRANCH_RESULTS, MAX_BRANCH_RESULTS),
	)
	return [(row.get("name"),) for row in rows if row.get("name")]


def _reserved_enabled_branches(profile_name=None):
	"""Return Branch names already bound by enabled setups, excluding the current setup."""
	rows = frappe.get_list(
		"RetailEdge Branch Profile",
		filters={"enabled": 1},
		fields=["name", "branch"],
		limit_page_length=0,
		order_by="branch asc",
	)
	return sorted(
		{
			row.get("branch")
			for row in rows
			if row.get("branch") and row.get("name") != profile_name
		}
	)
