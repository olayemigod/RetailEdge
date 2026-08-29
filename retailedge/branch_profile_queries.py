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
	"""Return unassigned ERPNext Branch masters for ordinary Branch Setup editing.

	ERPNext v16 Branch is global and has no native Company field. RetailEdge
	Branch Setup therefore establishes the Company↔Branch mapping. Ordinary setup
	creation/editing deliberately hides Branches that already have any mapping,
	including disabled historical mappings, so an administrator cannot silently
	reassign a previously used Branch by picking it in a normal Link field.

	A deliberate historical reassignment uses ``search_reassignment_target_branches``
	and the controlled server action instead.
	"""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	company = str(filters.get("company") or "").strip()
	if not company:
		return []

	profile_name = str(filters.get("profile_name") or "").strip()
	return _search_branch_candidates(
		txt=txt,
		start=start,
		page_len=page_len,
		profile_name=profile_name,
		exclude_mode="assigned",
	)


@frappe.whitelist()
@validate_and_sanitize_search_inputs
def search_reassignment_target_branches(doctype, txt, searchfield, start, page_len, filters):
	"""Return Branches that may be targets of an explicit controlled reassignment.

	The current Branch remains selectable so a Branch can deliberately move to a
	different Company. Disabled historical mappings do not reserve a Branch
	forever; only another *enabled* Branch Setup blocks the controlled target.
	Backend validation and active-session checks remain authoritative.
	"""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	company = str(filters.get("company") or "").strip()
	if not company:
		return []

	profile_name = str(filters.get("profile_name") or "").strip()
	return _search_branch_candidates(
		txt=txt,
		start=start,
		page_len=page_len,
		profile_name=profile_name,
		exclude_mode="active",
	)


@frappe.whitelist()
@validate_and_sanitize_search_inputs
def search_configured_company_branches(doctype, txt, searchfield, start, page_len, filters):
	"""Return enabled Branch Setup mappings for one Company.

	This query is used by operational setup such as Branch Assignment. It never
	guesses Company ownership from the ERPNext Branch master; the enabled
	RetailEdge Branch Setup Company↔Branch mapping is authoritative.
	"""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	company = str(filters.get("company") or "").strip()
	if not company:
		return []
	start = max(cint(start), 0)
	page_len = min(cint(page_len) or MAX_BRANCH_RESULTS, MAX_BRANCH_RESULTS)
	profile_filters = {"company": company, "enabled": 1}
	if txt:
		profile_filters["branch"] = ["like", f"%{txt}%"]
	rows = frappe.get_list(
		"RetailEdge Branch Profile",
		filters=profile_filters,
		fields=["branch"],
		order_by="branch asc",
		limit_start=start,
		limit_page_length=page_len,
	)
	branches = [row.get("branch") for row in rows if row.get("branch")]
	if not branches:
		return []
	visible = set(
		frappe.get_list(
			"Branch",
			filters={"name": ["in", branches]},
			pluck="name",
			limit_page_length=min(len(branches), MAX_BRANCH_RESULTS),
		)
		or []
	)
	return [(branch,) for branch in branches if branch in visible]


def _search_branch_candidates(*, txt, start, page_len, profile_name, exclude_mode):
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
		if exclude_mode == "active":
			excluded = _active_candidate_branches(names, profile_name=profile_name)
		else:
			excluded = _assigned_candidate_branches(names, profile_name=profile_name)
		available.extend(name for name in names if name not in excluded)

		row_count = len(rows)
		raw_start += row_count
		scanned += row_count
		if row_count < chunk_size:
			break

	return [(name,) for name in available[filtered_start:needed]]


def _assigned_candidate_branches(branch_names, profile_name=None):
	"""Return any historical/current mappings for bounded Branch candidates."""
	return _candidate_branches(branch_names, profile_name=profile_name, active_only=False)


def _active_candidate_branches(branch_names, profile_name=None):
	"""Return enabled mappings for bounded controlled-reassignment candidates."""
	return _candidate_branches(branch_names, profile_name=profile_name, active_only=True)


def _candidate_branches(branch_names, *, profile_name=None, active_only=False):
	branch_names = [name for name in dict.fromkeys(branch_names or []) if name]
	if not branch_names:
		return set()

	filters = {"branch": ["in", branch_names]}
	if active_only:
		filters["enabled"] = 1
	rows = frappe.get_list(
		"RetailEdge Branch Profile",
		filters=filters,
		fields=["name", "branch", "company", "enabled"],
		limit_page_length=min(max(len(branch_names) * 2, MAX_BRANCH_RESULTS), MAX_BRANCH_SCAN_RESULTS),
		order_by="branch asc",
	)
	return {
		row.get("branch")
		for row in rows
		if row.get("branch") and row.get("name") != profile_name
	}


# Compatibility alias retained for earlier PR #41 contracts.
def _reserved_candidate_branches(branch_names, profile_name=None):
	return _assigned_candidate_branches(branch_names, profile_name=profile_name)
