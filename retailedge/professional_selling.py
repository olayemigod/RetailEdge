from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import nowdate

from retailedge.guided_pricing import resolve_price_list_context
from retailedge.operating_context import get_operating_context


SELLING_DOCUMENTS: tuple[dict[str, Any], ...] = (
	{
		"key": "quotation",
		"doctype": "Quotation",
		"label": "Quotation",
		"stage": "Quote",
		"date_field": "transaction_date",
		"party_field": "party_name",
		"party_type_field": "quotation_to",
		"supports_shipping_rule": True,
		"supports_source_warehouse": False,
		"native_route": "/app/quotation",
	},
	{
		"key": "sales-order",
		"doctype": "Sales Order",
		"label": "Sales Order",
		"stage": "Order",
		"date_field": "transaction_date",
		"party_field": "customer",
		"supports_shipping_rule": True,
		"supports_source_warehouse": True,
		"native_route": "/app/sales-order",
	},
	{
		"key": "delivery-note",
		"doctype": "Delivery Note",
		"label": "Delivery Note",
		"stage": "Delivery",
		"date_field": "posting_date",
		"party_field": "customer",
		"supports_shipping_rule": True,
		"supports_source_warehouse": True,
		"native_route": "/app/delivery-note",
	},
)

_DOCUMENT_BY_KEY = {row["key"]: row for row in SELLING_DOCUMENTS}
_DOCUMENT_BY_DOCTYPE = {row["doctype"]: row for row in SELLING_DOCUMENTS}


def get_selling_document_definition(value: str) -> dict[str, Any]:
	key = str(value or "").strip()
	definition = _DOCUMENT_BY_KEY.get(key) or _DOCUMENT_BY_DOCTYPE.get(key)
	if not definition:
		frappe.throw(_("Unsupported Professional Selling document: {0}").format(key))
	return dict(definition)


def _doctype_available(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype))


def _permission(doctype: str, ptype: str) -> bool:
	try:
		return bool(_doctype_available(doctype) and frappe.has_permission(doctype, ptype))
	except Exception:
		return False


def _field_exists(doctype: str, fieldname: str) -> bool:
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def _document_capability(definition: dict[str, Any]) -> dict[str, Any]:
	doctype = definition["doctype"]
	available = _doctype_available(doctype)
	return {
		**definition,
		"available": available,
		"can_read": _permission(doctype, "read"),
		"can_create": _permission(doctype, "create"),
		"shipping_rule_field": available and _field_exists(doctype, "shipping_rule"),
		"selling_price_list_field": available and _field_exists(doctype, "selling_price_list"),
		"source_warehouse_field": available and _field_exists(doctype, "set_warehouse"),
	}


@frappe.whitelist()
def get_professional_selling_context() -> dict[str, Any]:
	"""Return a read-only, permission-aware Quote → Order → Delivery context.

	ERPNext remains authoritative for document persistence, pricing rules, taxes,
	Shipping Rules, stock and accounting. This endpoint only describes the
	available workflow and current RetailEdge Operating Context.
	"""
	operating = get_operating_context() or {}
	company = str(operating.get("company") or "").strip()
	branch = str(operating.get("branch") or "").strip()
	pricing: dict[str, Any] = {}
	if company and _permission("Price List", "read"):
		pricing = resolve_price_list_context(
			mode="selling",
			company=company,
			branch=branch,
			user=frappe.session.user,
		)

	documents = [_document_capability(row) for row in SELLING_DOCUMENTS]
	return {
		"operating": {
			"company": company,
			"branch": branch,
			"default_stock_location": operating.get("default_stock_location") or "",
		},
		"pricing": {
			"price_list": pricing.get("price_list") or "",
			"source": pricing.get("source") or "",
			"allow_rate_change": bool(pricing.get("allow_rate_change", True)),
		},
		"documents": documents,
		"today": nowdate(),
		"shipping": {
			"doctype": "Shipping Rule",
			"available": _doctype_available("Shipping Rule"),
			"can_read": _permission("Shipping Rule", "read"),
			"policy": "erpnext_native",
		},
		"safety": {
			"draft_first": True,
			"submitted_documents_immutable": True,
			"erpnext_pricing_authoritative": True,
			"erpnext_shipping_rule_authoritative": True,
		},
		"user_name": frappe.get_user().get_fullname() if getattr(frappe, "session", None) else "",
	}


@frappe.whitelist()
def get_recent_selling_documents(document: str, limit: int = 8) -> list[dict[str, Any]]:
	"""Return a bounded recent-document list using native Frappe permissions."""
	definition = get_selling_document_definition(document)
	doctype = definition["doctype"]
	if not _permission(doctype, "read"):
		frappe.throw(_("You do not have permission to view {0}.").format(doctype), frappe.PermissionError)

	limit = max(1, min(int(limit or 8), 20))
	meta = frappe.get_meta(doctype)
	fields = ["name", "docstatus", "modified"]
	for candidate in (
		definition["party_field"],
		definition["date_field"],
		"status",
		"grand_total",
		"currency",
		"shipping_rule",
	):
		if candidate not in fields and meta.has_field(candidate):
			fields.append(candidate)

	rows = frappe.get_list(
		doctype,
		fields=fields,
		order_by="modified desc",
		limit_page_length=limit,
	)
	return [dict(row) for row in rows]
