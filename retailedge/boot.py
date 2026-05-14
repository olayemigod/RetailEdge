from __future__ import annotations

import frappe

from retailedge.cost_visibility import get_cost_price_visibility_context
from retailedge.integrations.coreedge import get_coreedge_status
from retailedge.posting_date_control import get_posting_date_context
from retailedge.utils.settings import get_retailedge_settings


def boot_session(bootinfo):
	bootinfo.retailedge = {}

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
