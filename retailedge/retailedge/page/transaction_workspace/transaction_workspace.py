from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.branch_context import resolve_branch_from_opening_shift, resolve_branch_from_pos_profile
from retailedge.cashier_context import find_open_pos_opening_shift
from retailedge.operating_context import get_operating_context
from retailedge.pos_runtime import get_pos_runtime_capabilities

TRANSACTION_ACTIONS: tuple[dict[str, str], ...] = (
	{"key": "sales-invoice", "label": "Sales Invoice", "doctype": "Sales Invoice", "kind": "sell"},
	{"key": "sales-order", "label": "Sales Order", "doctype": "Sales Order", "kind": "sell"},
	{"key": "delivery-note", "label": "Delivery Note", "doctype": "Delivery Note", "kind": "sell"},
	{"key": "purchase-invoice", "label": "Purchase Invoice", "doctype": "Purchase Invoice", "kind": "buy"},
	{"key": "purchase-order", "label": "Purchase Order", "doctype": "Purchase Order", "kind": "buy"},
	{"key": "purchase-receipt", "label": "Purchase Receipt", "doctype": "Purchase Receipt", "kind": "buy"},
	{"key": "stock-entry", "label": "Stock Transfer", "doctype": "Stock Entry", "kind": "stock"},
)


def _can_create(doctype: str) -> bool:
	try:
		return bool(frappe.db.exists("DocType", doctype) and frappe.has_permission(doctype, "create"))
	except Exception:
		return False


def _doctype_exists(doctype: str | None) -> bool:
	return bool(doctype and frappe.db.exists("DocType", doctype))


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _validate_pos_profile(profile_name: str, *, company: str, branch: str) -> dict[str, str]:
	profile_name = _clean(profile_name)
	if not profile_name:
		return {"name": "", "company": "", "branch": ""}
	if not frappe.db.exists("POS Profile", profile_name):
		frappe.throw(_("POS Profile {0} is not available.").format(profile_name))
	profile = frappe.get_doc("POS Profile", profile_name)
	if not frappe.has_permission("POS Profile", "read", doc=profile):
		frappe.throw(_("You do not have access to POS Profile {0}.").format(profile_name), frappe.PermissionError)

	profile_company = _clean(getattr(profile, "company", None))
	if profile_company and profile_company != company:
		frappe.throw(_("POS Profile {0} does not belong to the current Operating Company.").format(profile_name))

	resolved = resolve_branch_from_pos_profile(profile_name, company=company or None)
	profile_branch = _clean(resolved.get("branch"))
	if profile_branch and branch and profile_branch != branch:
		frappe.throw(_("POS Profile {0} does not match the current Operating Branch.").format(profile_name))
	return {"name": profile_name, "company": profile_company, "branch": profile_branch}


@frappe.whitelist()
def get_transaction_workspace_context() -> dict[str, Any]:
	"""Return a permission-aware transaction host context without writing state."""
	operating = get_operating_context() or {}
	pos = get_pos_runtime_capabilities()

	actions = [
		{**action, "can_create": True}
		for action in TRANSACTION_ACTIONS
		if _can_create(action["doctype"])
	]

	return {
		"operating": {
			"company": operating.get("company") or "",
			"branch": operating.get("branch") or "",
			"default_pos_profile": operating.get("default_pos_profile") or "",
			"default_stock_location": operating.get("default_stock_location") or "",
		},
		"pos": {
			"provider": pos.provider,
			"start_link_type": pos.start_link_type,
			"start_target": pos.start_target,
			"start_url": pos.start_url,
			"opening_doctype": pos.opening_doctype if _doctype_exists(pos.opening_doctype) else None,
			"closing_doctype": pos.closing_doctype if _doctype_exists(pos.closing_doctype) else None,
			"embedded": False,
		},
		"actions": actions,
		"user_name": frappe.get_user().get_fullname() if getattr(frappe, "session", None) else "",
	}


@frappe.whitelist()
def prepare_pos_launch() -> dict[str, Any]:
	"""Validate the current Operating Context before the browser enters POS.

	This method is intentionally read-only. It does not create, update, close or
	submit POS shifts and does not mutate the session Operating Context. POSNext
	continues to own its POS transaction runtime.
	"""
	operating = get_operating_context() or {}
	company = _clean(operating.get("company"))
	branch = _clean(operating.get("branch"))
	default_profile = _clean(operating.get("default_pos_profile"))
	if not company or not branch:
		frappe.throw(_("Choose an Operating Company and Branch before starting POS."))

	pos = get_pos_runtime_capabilities()
	if not (pos.start_target or pos.start_url):
		frappe.throw(_("No POS provider is available for this site."))

	validated_profile = _validate_pos_profile(default_profile, company=company, branch=branch) if default_profile else {}
	active_shift: dict[str, str] = {}

	if pos.provider == "posnext":
		opening_shift = find_open_pos_opening_shift(user=frappe.session.user, company=company)
		if opening_shift:
			shift_company = _clean(getattr(opening_shift, "company", None))
			if shift_company and shift_company != company:
				frappe.throw(_("The active POS shift belongs to another Company. Close it before starting POS here."))
			resolved = resolve_branch_from_opening_shift(opening_shift, company=shift_company or company)
			shift_branch = _clean(resolved.get("branch"))
			if not shift_branch or shift_branch != branch:
				frappe.throw(_("The active POS shift does not match the current Operating Branch. Close it before starting POS here."))
			shift_profile = _clean(getattr(opening_shift, "pos_profile", None))
			if default_profile and shift_profile and shift_profile != default_profile:
				frappe.throw(_("The active POS shift uses a different POS Profile from the current Branch Setup."))
			if shift_profile:
				_validate_pos_profile(shift_profile, company=company, branch=branch)
			active_shift = {
				"name": _clean(getattr(opening_shift, "name", None)),
				"company": shift_company,
				"branch": shift_branch,
				"pos_profile": shift_profile,
			}

	return {
		"provider": pos.provider,
		"start_link_type": pos.start_link_type,
		"start_target": pos.start_target,
		"start_url": pos.start_url,
		"operating": {"company": company, "branch": branch},
		"pos_profile": active_shift.get("pos_profile") or validated_profile.get("name") or "",
		"active_shift": active_shift,
	}
