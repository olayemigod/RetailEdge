from __future__ import annotations

import re
from urllib.parse import quote

import frappe

from retailedge.api.permission import has_app_permission
from retailedge.branch_context import has_field, validate_user_branch_access
from retailedge.ui_identity import get_retailedge_ui_identity
from retailedge.workspace_home import HOME_SECTIONS, HOME_WORKSPACE_ITEMS, WorkspaceHomeItem, target_exists


SECTION_META = {
	"Operations": {
		"icon": "store",
		"description": "Run sales, cash, stock and statement activities.",
	},
	"Review & Approvals": {
		"icon": "check-circle",
		"description": "Resolve exceptions and complete controlled reviews.",
	},
	"Reports & Analytics": {
		"icon": "chart",
		"description": "Understand branch, sales, cash, bank and stock performance.",
	},
	"Accounting / Ledger Bridge": {
		"icon": "ledger",
		"description": "Move verified operational evidence into ERPNext accounting workflows.",
	},
	"Setup / Configuration": {
		"icon": "settings",
		"description": "Configure branches, expenses, statements and retail defaults.",
	},
	"Admin / Maintenance": {
		"icon": "tools",
		"description": "Inspect integrity, failures and administrator-only utilities.",
	},
}


def _slug(value: str) -> str:
	return re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")


def _route_for(item: WorkspaceHomeItem) -> str:
	if item.link_type == "URL":
		return item.url or item.link_to
	if item.link_type == "Report":
		return f"/app/query-report/{quote(item.link_to, safe='')}"
	if item.link_type == "DocType":
		return f"/app/{_slug(item.link_to)}"
	if item.link_type == "Workspace":
		return f"/app/{_slug(item.link_to)}"
	return f"/app/{item.link_to.strip('/')}"


def _document_permission(doctype: str, name: str) -> bool:
	try:
		if not frappe.db.exists(doctype, name):
			return False
		doc = frappe.get_doc(doctype, name)
		return bool(frappe.has_permission(doctype, ptype="read", doc=doc))
	 except Exception:
		return False


def _can_access(item: WorkspaceHomeItem) -> bool:
	if not target_exists(item):
		return False
	if item.link_type == "URL":
		return True
	if item.link_type == "DocType":
		try:
			return bool(frappe.has_permission(item.link_to, ptype="read"))
		except Exception:
			return False
	if item.link_type in {"Report", "Page", "Workspace"}:
		return _document_permission(item.link_type, item.link_to)
	return False


def _serialize_item(item: WorkspaceHomeItem) -> dict:
	return {
		"label": item.label,
		"link_type": item.link_type,
		"link_to": item.link_to,
		"route": _route_for(item),
		"section": item.section,
		"source": item.source,
		"audience": item.audience,
		"icon": {
			"Operations": "play",
			"Review & Approvals": "check-circle",
			"Reports & Analytics": "chart",
			"Accounting / Ledger Bridge": "ledger",
			"Setup / Configuration": "settings",
			"Admin / Maintenance": "tools",
		}.get(item.section, "list"),
	}


def _sections() -> list[dict]:
	result = []
	for section in HOME_SECTIONS:
		items = [
			_serialize_item(item)
			for item in sorted(
				(candidate for candidate in HOME_WORKSPACE_ITEMS if candidate.section == section),
				key=lambda candidate: candidate.priority,
			)
			if _can_access(item)
		]
		if not items:
			continue
		meta = SECTION_META.get(section, {})
		result.append(
			{
				"key": _slug(section),
				"label": section,
				"icon": meta.get("icon") or "layers",
				"description": meta.get("description") or "",
				"items": items,
			}
		)
	return result


def _company_for_branch(branch: str, fallback: str) -> str:
	if not branch or not frappe.db.exists("DocType", "Branch") or not has_field("Branch", "company"):
		return fallback
	try:
		return frappe.db.get_value("Branch", branch, "company") or fallback
	except Exception:
		return fallback


@frappe.whitelist()
def get_home_context(branch: str | None = None, company: str | None = None) -> dict:
	if not has_app_permission():
		frappe.throw("You do not have access to RetailEdge.", frappe.PermissionError)

	identity = get_retailedge_ui_identity()
	company = company or identity.get("company") or ""
	active_branch = branch or identity.get("branch") or ""
	if active_branch:
		company = _company_for_branch(active_branch, company)
		validate_user_branch_access(
			active_branch,
			user=frappe.session.user,
			company=company,
			throw=True,
		)

	sections = _sections()
	item_count = sum(len(section["items"]) for section in sections)
	return {
		"identity": identity,
		"company": company,
		"active_branch": active_branch,
		"branches": identity.get("branches") or [],
		"can_switch_branch": bool(identity.get("can_switch_branch")),
		"sections": sections,
		"summary": {
			"accessible_actions": item_count,
			"workspace_sections": len(sections),
			"permitted_branches": len(identity.get("branches") or []),
		},
		"context_note": (
			"The branch selection currently filters this RetailEdge Home view. "
			"Existing ERPNext document defaults and accounting behaviour are unchanged."
		),
	}
