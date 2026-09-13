from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

from retailedge.professional_selling import MAX_LINK_RESULTS, _coerce_values, _permission, _validate_context


@frappe.whitelist()
def search_professional_selling_sources(
	target: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	"""Return permission-aware submitted source documents for native ERPNext mapping.

	This function never maps or mutates a source. It only narrows the Link search
	to source documents compatible with the requested target and current Company.
	"""
	target = str(target or "").strip()
	values = _coerce_values(values)
	company, _branch, _warehouse = _validate_context(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))

	if target == "sales-order":
		if not _permission("Sales Order", "create") or not _permission("Quotation", "read"):
			frappe.throw(_("You do not have permission to create a Sales Order from Quotation."), frappe.PermissionError)
		filters: dict[str, Any] = {
			"docstatus": 1,
			"quotation_to": "Customer",
			"company": company,
			"status": ["not in", ["Ordered", "Lost", "Cancelled", "Expired"]],
		}
		return search_link(
			"Quotation",
			txt or "",
			filters=filters,
			page_length=limit,
			reference_doctype="Sales Order",
			link_fieldname="quotation",
		)

	if target == "delivery-note":
		if not _permission("Delivery Note", "create") or not _permission("Sales Order", "read"):
			frappe.throw(_("You do not have permission to create a Delivery Note from Sales Order."), frappe.PermissionError)
		filters = {
			"docstatus": 1,
			"company": company,
			"status": ["not in", ["Closed", "Completed", "Cancelled"]],
			"delivery_status": ["!=", "Fully Delivered"],
		}
		return search_link(
			"Sales Order",
			txt or "",
			filters=filters,
			page_length=limit,
			reference_doctype="Delivery Note",
			link_fieldname="against_sales_order",
		)

	frappe.throw(_("Unsupported Professional Selling conversion target: {0}").format(target))
	return []
