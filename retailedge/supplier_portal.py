from __future__ import annotations

from typing import Any
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils.user import is_website_user

from erpnext.controllers.website_list_for_contact import get_parents_for_user, get_transaction_list

from retailedge.supplier_portal_collaboration import (
	get_purchase_order_activity_states,
	purchase_order_acknowledgement_allowed,
)
from retailedge.supplier_portal_financial import get_supplier_payables_summary

MAX_RECENT_ROWS = 5

SUPPLIER_SECTIONS: tuple[dict[str, str], ...] = (
	{
		"key": "rfqs",
		"doctype": "Request for Quotation",
		"route": "/rfq",
		"label": "Requests for Quotation",
	},
	{
		"key": "supplier_quotations",
		"doctype": "Supplier Quotation",
		"route": "/supplier-quotations",
		"label": "Supplier Quotations",
	},
	{
		"key": "purchase_orders",
		"doctype": "Purchase Order",
		"route": "/purchase-orders",
		"label": "Purchase Orders",
	},
	{
		"key": "purchase_invoices",
		"doctype": "Purchase Invoice",
		"route": "/purchase-invoices",
		"label": "Purchase Invoices",
	},
)


def _assert_supplier_portal_user() -> list[str]:
	if frappe.session.user == "Guest" or not is_website_user():
		frappe.throw(_("Please sign in with your supplier account."), frappe.PermissionError)
	if "Supplier" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("Supplier Portal access requires the Supplier role."), frappe.PermissionError)
	suppliers = [str(name) for name in get_parents_for_user("Supplier") if name]
	if not suppliers:
		frappe.throw(_("Your account is not linked to a Supplier record."), frappe.PermissionError)
	return suppliers


def _native_recent(section: dict[str, str]) -> list[Any]:
	if not frappe.db.exists("DocType", section["doctype"]):
		return []
	return list(
		get_transaction_list(
			doctype=section["doctype"],
			limit_start=0,
			limit_page_length=MAX_RECENT_ROWS,
			order_by="creation desc",
		)
		or []
	)


def _row_url(section: dict[str, str], name: str) -> str:
	if section["doctype"] == "Request for Quotation":
		return section["route"]
	return f'{section["route"]}/{quote(str(name), safe="")}'


def _section_context(section: dict[str, str], suppliers: list[str]) -> dict[str, Any]:
	recent = _native_recent(section)
	activity_states = (
		get_purchase_order_activity_states([row.name for row in recent], suppliers)
		if section["doctype"] == "Purchase Order"
		else {}
	)
	rows = []
	for row in recent:
		state = activity_states.get(str(row.name), {})
		rows.append(
			{
				"name": row.name,
				"status": getattr(row, "status", "") or "",
				"date": (
					getattr(row, "transaction_date", None)
					or getattr(row, "posting_date", None)
					or getattr(row, "schedule_date", None)
				),
				"grand_total": getattr(row, "grand_total", 0) or 0,
				"currency": getattr(row, "currency", "") or "",
				"company": getattr(row, "company", "") or "",
				"document_url": _row_url(section, row.name),
				"can_acknowledge": (
					section["doctype"] == "Purchase Order"
					and not bool(state.get("acknowledged"))
					and purchase_order_acknowledgement_allowed(row)
				),
				"acknowledged": bool(state.get("acknowledged")),
				"acknowledged_on": state.get("acknowledged_on"),
				"acknowledgement_note": state.get("acknowledgement_note") or "",
				"message_count": int(state.get("message_count") or 0),
				"recent_messages": list(state.get("recent_messages") or []),
			}
		)
	return {
		**section,
		"recent": rows,
		"recent_count": len(rows),
	}


def get_supplier_portal_context() -> dict[str, Any]:
	suppliers = _assert_supplier_portal_user()
	sections = [_section_context(section, suppliers) for section in SUPPLIER_SECTIONS]
	payables = get_supplier_payables_summary(suppliers)

	companies = {
		str(balance.get("company") or "")
		for balance in payables.get("balances", [])
		if balance.get("company")
	}
	for section in sections:
		companies.update(str(row.get("company") or "") for row in section["recent"] if row.get("company"))
	company_name = next(iter(companies)) if len(companies) == 1 else ""

	return {
		"supplier_names": suppliers,
		"supplier_label": ", ".join(suppliers),
		"user_full_name": frappe.utils.get_fullname(frappe.session.user),
		"sections": sections,
		"payables": payables,
		"company_name": company_name,
		"routes": {
			"supplier_portal": "/supplier_portal",
			"account_statement": "/supplier_account_statement",
		},
		"source_of_truth": "ERPNext Supplier portal transactions, Purchase Invoice, Payment Entry and Payment Ledger Entry",
	}
