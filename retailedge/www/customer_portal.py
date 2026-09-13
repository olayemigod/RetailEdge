from __future__ import annotations

from urllib.parse import quote

import frappe

from retailedge.customer_portal import get_customer_portal_context
from retailedge.customer_portal_financial import get_customer_advance_summary

no_cache = 1


def _advance_statement_section(advance_summary: dict) -> dict:
	rows = []
	for balance in list(advance_summary.get("balances") or [])[:5]:
		company = str(balance.get("company") or "")
		currency = str(balance.get("currency") or "")
		count = int(balance.get("count") or 0)
		rows.append(
			{
				"name": f"?company={quote(company, safe='')}",
				"project_name": f"{company} · Available Advance" if company else "Available Advance",
				"status": f"{count} unallocated payment{'s' if count != 1 else ''}",
				"date": None,
				"grand_total": balance.get("available_advance") or 0,
				"currency": currency,
				"outstanding_amount": 0,
				"percent_complete": 0,
				"download_url": "",
				"can_pay_online": False,
				"can_respond_to_quotation": False,
				"can_message_quotation": False,
			}
		)
	return {
		"key": "financial_statement",
		"doctype": "",
		"route": "/customer_account_statement",
		"label": "Advances & Statements",
		"count": int(advance_summary.get("balance_count") or 0),
		"recent": rows,
	}


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/customer_portal"
		raise frappe.Redirect

	portal = get_customer_portal_context()
	advance_summary = get_customer_advance_summary(portal.get("customer_names") or [])
	portal["advance_summary"] = advance_summary
	portal.setdefault("routes", {})["account_statement"] = "/customer_account_statement"
	portal.setdefault("sections", []).append(_advance_statement_section(advance_summary))
	company_name = str(frappe.defaults.get_global_default("default_company") or "").strip()
	context.no_cache = 1
	context.show_sidebar = True
	context.title = "Customer Portal"
	context.portal = portal
	context.company_name = company_name
	context.user_full_name = portal.get("user_full_name") or ""
	context.customer_label = portal.get("customer_label") or ""
	return context
