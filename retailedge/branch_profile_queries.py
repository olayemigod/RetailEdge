from __future__ import annotations

import frappe
from frappe.desk.search import validate_and_sanitize_search_inputs
from frappe.utils import cint


MAX_BRANCH_RESULTS = 20
BRANCH_SCAN_CHUNK = 40
MAX_BRANCH_SCAN_RESULTS = 200


@frappe.whitelist()
@validate_and_sanitize_search_inputs
def search_available_branch_setup_branches(doctype, txt, searchfield, start, page_len, filters):
	"""Return available Branch masters for one RetailEdge Branch Setup.

	ERPNext v16 Branch is global and has no native Company field. RetailEdge
	Branch Setup owns the Company↔Branch binding, so Company must be selected
	first and Branches already reserved by another enabled setup are hidden.
	Backend validation remains authoritative for duplicate/cross-company safety.
	"""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	company = str(filters.get("company") or "").strip()
	if not company:
		return []

	profile_name = str(filters.get("profile_name") or "").strip()
	filtered_start = max(cint(start), 0)
	requested = min(cint(page_len) or MAX_BRANCH_RESULTS, MAX_BRANCH_RESULTS)
	needed = filtered_start + requested
	available = []
	raw_start = 0
	scanned = 0
	branch_filters = []
	if txt:
		branch_filters.append(["Branch", "name", "like", f"%{txt}%"])

	while len(available) < needed and scanned < MAX_BRANCH_SCAN_RESULTS:
		chunk_size = min(BRANCH_SCAN_CHUNK, MAX_BRANCH_SCAN_RESULTS - scanned)
		rows = frappe.get_list(
			"Branch",
			filters=branch_filters,
			fields=["name"],
			order_by="name asc",
			limit_start=raw_start,
			limit_page_length=chunk_size,
		)
		if not rows:
			break

		names = [row.get("name") for row in rows if row.get("name")]
		reserved = _reserved_candidate_branches(names, profile_name=profile_name)
		available.extend(name for name in names if name not in reserved)

		row_count = len(rows)
		raw_start += row_count
		scanned += row_count
		if row_count < chunk_size:
			break

	return [(name,) for name in available[filtered_start:needed]]


def _reserved_candidate_branches(branch_names, profile_name=None):
	"""Return enabled bindings only for the bounded Branch candidates being displayed."""
	branch_names = [name for name in dict.fromkeys(branch_names or []) if name]
	if not branch_names:
		return set()

	rows = frappe.get_list(
		"RetailEdge Branch Profile",
		filters={"enabled": 1, "branch": ["in", branch_names]},
		fields=["name", "branch"],
		limit_page_length=min(max(len(branch_names) * 2, MAX_BRANCH_RESULTS), MAX_BRANCH_SCAN_RESULTS),
		order_by="branch asc",
	)
	return {
		row.get("branch")
		for row in rows
		if row.get("branch") and row.get("name") != profile_name
	}
