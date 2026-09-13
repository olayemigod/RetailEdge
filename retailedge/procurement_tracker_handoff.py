from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.operating_context import get_operating_context
from retailedge.reporting_scope import has_unrestricted_report_scope, validate_report_scope

PROCUREMENT_TRACKER_REPORT = "Procurement Tracker"


def _can_open_report(report_name: str) -> bool:
	try:
		return bool(
			frappe.db.exists("Report", report_name)
			and frappe.has_permission("Report", "read", doc=report_name)
		)
	except Exception:
		return False


def _resolve_company(company: str | None = None) -> str:
	operating = get_operating_context() or {}
	resolved = str(
		company or operating.get("company") or frappe.defaults.get_user_default("Company") or ""
	).strip()
	if not resolved:
		return ""
	if not frappe.db.exists("Company", resolved):
		frappe.throw(_("Company {0} does not exist.").format(resolved))
	if not frappe.has_permission("Company", "read", doc=resolved):
		frappe.throw(
			_("You do not have permission to use Company {0}.").format(resolved), frappe.PermissionError
		)
	return resolved


@frappe.whitelist()
def get_procurement_tracker_handoff(
	company: str | None = None,
	branch: str | None = None,
) -> dict[str, Any]:
	"""Return a safe native Procurement Tracker handoff capability.

	ERPNext v16 Procurement Tracker is company/cost-center/project/date scoped and
	does not provide a Branch filter. RetailEdge therefore exposes it only when
	the current user has unrestricted reporting access for the selected Company
	and the current purchasing view is company-wide. No Procurement Tracker rows
	are executed or reproduced here.
	"""
	resolved_company = _resolve_company(company)
	resolved_branch = str(branch or "").strip()
	if resolved_branch and resolved_company:
		validate_report_scope(
			company=resolved_company,
			branch=resolved_branch,
			user=frappe.session.user,
		)

	report_readable = _can_open_report(PROCUREMENT_TRACKER_REPORT)
	unrestricted_company_scope = bool(
		resolved_company
		and has_unrestricted_report_scope(
			resolved_company,
			user=frappe.session.user,
		)
	)
	purchase_order_readable = bool(frappe.has_permission("Purchase Order", "read"))
	company_wide_view = not resolved_branch
	available = bool(
		resolved_company
		and report_readable
		and unrestricted_company_scope
		and company_wide_view
		and purchase_order_readable
	)

	if not resolved_company:
		reason = _("Choose a Company before opening Procurement Tracker.")
	elif not report_readable:
		reason = _("ERPNext Procurement Tracker is unavailable for your current permissions.")
	elif not unrestricted_company_scope:
		reason = _("Procurement Tracker is company-wide and is hidden for Branch-restricted access.")
	elif resolved_branch:
		reason = _("Clear the Branch filter before opening the company-wide Procurement Tracker.")
	elif not purchase_order_readable:
		reason = _("You do not have permission to read Purchase Orders.")
	else:
		reason = ""

	return {
		"available": available,
		"company": resolved_company,
		"branch": resolved_branch,
		"report": PROCUREMENT_TRACKER_REPORT,
		"reason": reason,
		"company_wide_only": True,
		"source_of_truth": "ERPNext Procurement Tracker Script Report",
		"branch_policy": "unrestricted-company-scope-and-no-selected-branch",
	}
