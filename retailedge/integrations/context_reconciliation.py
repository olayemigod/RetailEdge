from __future__ import annotations

import frappe
from frappe.utils import cint


def get_context_reconciliation_rows(company: str | None = None) -> list[dict]:
	"""
	Return RetailEdge Company/Branch identities in the CoreEdge reconciliation shape.

	RetailEdge Branch Profile remains the authoritative Company -> ERPNext Branch
	binding. This helper is read-only and does not import or call CoreEdge.
	"""
	if not frappe.db.exists("DocType", "RetailEdge Branch Profile"):
		return []

	filters = {}
	if company:
		filters["company"] = company

	profiles = frappe.get_all(
		"RetailEdge Branch Profile",
		filters=filters,
		fields=["name", "company", "branch", "enabled", "modified"],
		limit_page_length=0,
		order_by="enabled desc, modified desc, name asc",
	)

	# A disabled historical profile may coexist with a newer enabled profile.
	# Reconciliation is about the Company + Branch identity, so emit one row and
	# prefer the enabled/current profile deterministically.
	selected: dict[tuple[str, str], dict] = {}
	for profile in profiles:
		profile_company = str(profile.get("company") or "").strip()
		branch = str(profile.get("branch") or "").strip()
		if not profile_company or not branch:
			continue

		key = (profile_company, branch)
		current = selected.get(key)
		if current is None or _profile_priority(profile) > _profile_priority(current):
			selected[key] = profile

	rows = []
	for (profile_company, branch), profile in sorted(selected.items()):
		identity = _get_branch_identity(branch)
		rows.append(
			{
				"local_doctype": "Branch",
				"local_name": branch,
				"local_label": identity["label"],
				"local_code": identity["code"],
				"company": profile_company,
				"active": bool(cint(profile.get("enabled"))),
				"source_profile": profile.get("name") or "",
			}
		)
	return rows


def _get_branch_identity(branch: str) -> dict:
	if not branch or not frappe.db.exists("Branch", branch):
		return {"label": branch, "code": ""}

	meta = frappe.get_meta("Branch")
	fields = ["name"]
	for fieldname in ("branch", "branch_name", "branch_code"):
		if meta.has_field(fieldname):
			fields.append(fieldname)

	values = frappe.db.get_value("Branch", branch, fields, as_dict=True) or {}
	label = (
		values.get("branch")
		or values.get("branch_name")
		or values.get("name")
		or branch
	)
	return {
		"label": str(label).strip(),
		"code": str(values.get("branch_code") or "").strip(),
	}


def _profile_priority(profile: dict) -> tuple[int, str, str]:
	return (
		1 if cint(profile.get("enabled")) else 0,
		str(profile.get("modified") or ""),
		str(profile.get("name") or ""),
	)
