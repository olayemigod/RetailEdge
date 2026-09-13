from __future__ import annotations

import frappe
from frappe.utils import cint, cstr

from retailedge.operating_context import get_allowed_operating_contexts


@frappe.whitelist()
def search_banking_branches(
	txt: str | None = None,
	company: str | None = None,
	limit: int = 20,
):
	"""Return banking Branch options from RetailEdge's canonical operating context.

	ERPNext Branch is not guaranteed to have a Company field. RetailEdge Operating
	Context already handles that schema variation together with Branch permissions,
	User Permission restrictions, and enabled Branch Profile membership. Banking must
	reuse that authority rather than assuming ``Branch.company`` exists.
	"""
	company = cstr(company).strip()
	if not company:
		return []

	payload = get_allowed_operating_contexts(company=company) or {}
	branches = payload.get("branches") or []
	query = cstr(txt).strip().lower()
	safe_limit = min(max(cint(limit) or 20, 1), 50)

	results: list[dict[str, str]] = []
	for branch in branches:
		name = cstr(branch).strip()
		if not name:
			continue
		if query and query not in name.lower():
			continue
		results.append(
			{
				"value": name,
				"label": name,
				"description": company,
			}
		)
		if len(results) >= safe_limit:
			break
	return results
