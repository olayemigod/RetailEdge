from __future__ import annotations

import frappe

from retailedge.cost_visibility import get_cost_price_visibility_context
from retailedge.integrations.coreedge import get_coreedge_status
from retailedge.posting_date_control import get_posting_date_context
from retailedge.operating_context import get_allowed_operating_contexts, get_operating_context
from retailedge.utils.settings import get_retailedge_settings


def _company_identity(company: str) -> dict:
	company = str(company or "").strip()
	if not company or not frappe.db.exists("Company", company):
		return {"name": company, "label": company, "logo": ""}

	fields = ["name", "company_name"]
	meta = frappe.get_meta("Company")
	if meta.has_field("company_logo"):
		fields.append("company_logo")
	row = frappe.db.get_value("Company", company, fields, as_dict=True) or {}
	return {
		"name": row.get("name") or company,
		"label": row.get("company_name") or row.get("name") or company,
		"logo": row.get("company_logo") or "",
	}


def _populate_edgesuite_identity(bootinfo) -> None:
	try:
		operating = get_operating_context() or {}
		company = operating.get("company") or frappe.defaults.get_user_default("Company") or ""
		branch = operating.get("branch") or ""
		identity = _company_identity(company)
		allowed = get_allowed_operating_contexts(company=company) if company else {}
		payload = {
			"product_code": "retailedge",
			"product_name": "RetailEdge",
			"product_logo": "",
			"product_icon": "shopping-cart",
			"product_subtitle": "Retail operations & control",
			"tenant_name": identity.get("label") or company,
			"tenant_logo": identity.get("logo") or "",
			"tenant_icon": "building",
			"tenant_subtitle": "Business workspace",
			"active_company": company,
			"active_branch": branch,
			"branch_options": list(allowed.get("branches") or []),
			"can_switch_branch": bool(allowed.get("can_switch_branch")),
		}
		bootinfo["retailedge_ui_identity"] = payload
		shared = bootinfo.get("edgesuite_ui_identity") or {}
		shared["retailedge"] = payload
		bootinfo["edgesuite_ui_identity"] = shared
	except Exception:
		frappe.logger("retailedge.boot").exception("Failed to populate RetailEdge EdgeSuite identity")


def boot_session(bootinfo):
	bootinfo.retailedge = {}
	_populate_edgesuite_identity(bootinfo)

	for key, getter in {
		"posting_date": get_posting_date_context,
		"cost_visibility": get_cost_price_visibility_context,
		"coreedge": get_coreedge_status,
	}.items():
		try:
			bootinfo.retailedge[key] = getter()
		except Exception:
			bootinfo.retailedge[key] = {}
			frappe.logger("retailedge.boot").exception("Failed to populate RetailEdge boot context for %s", key)

	try:
		settings = get_retailedge_settings()
		bootinfo.retailedge["cashier_expense_settings"] = {
			"require_open_shift_for_cashier_expense": int(bool(getattr(settings, "require_open_shift_for_cashier_expense", 1))),
			"allow_cashier_expense_date_edit": int(bool(getattr(settings, "allow_cashier_expense_date_edit", 0))),
			"include_draft_cashier_expenses_in_cash_check": int(bool(getattr(settings, "include_draft_cashier_expenses_in_cash_check", 1))),
			"include_rejected_cashier_expenses_in_cash_check": int(bool(getattr(settings, "include_rejected_cashier_expenses_in_cash_check", 1))),
			"allow_cashier_expense_without_cash_account": int(bool(getattr(settings, "allow_cashier_expense_without_cash_account", 0))),
			"include_draft_cashier_expenses_in_daily_audit": int(bool(getattr(settings, "include_draft_cashier_expenses_in_daily_audit", 1))),
			"include_submitted_cashier_expenses_in_daily_audit": int(bool(getattr(settings, "include_submitted_cashier_expenses_in_daily_audit", 1))),
			"include_pending_ledger_cashier_expenses_in_daily_audit": int(bool(getattr(settings, "include_pending_ledger_cashier_expenses_in_daily_audit", 1))),
			"include_rejected_cashier_expenses_in_daily_audit": int(bool(getattr(settings, "include_rejected_cashier_expenses_in_daily_audit", 1))),
			"exclude_cancelled_cashier_expenses_from_daily_audit": int(bool(getattr(settings, "exclude_cancelled_cashier_expenses_from_daily_audit", 1))),
		}
	except Exception:
		bootinfo.retailedge["cashier_expense_settings"] = {}
		frappe.logger("retailedge.boot").exception(
			"Failed to populate RetailEdge boot context for cashier expense settings"
		)
