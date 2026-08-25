from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from erpnext.selling.doctype.sales_order.mapper import make_delivery_note as erpnext_make_delivery_note

from retailedge.branch_context import resolve_branch_from_warehouse, validate_user_branch_access
from retailedge.operating_context import get_operating_context
from retailedge.professional_quotation import _validate_shipping_rule
from retailedge.professional_selling import _assert_read, _permission


def _source_branch(doc) -> str:
	return str(doc.get("branch") or doc.get("retailedge_branch") or "").strip()


def _validate_source_against_operating_context(source) -> tuple[str, str]:
	company = str(source.get("company") or "").strip()
	if not company:
		frappe.throw(_("The Sales Order has no Company."))
	_assert_read("Company", company)

	branch = _source_branch(source)
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)

	operating = get_operating_context() or {}
	operating_company = str(operating.get("company") or "").strip()
	operating_branch = str(operating.get("branch") or "").strip()
	if operating_company and operating_company != company:
		frappe.throw(_("The Sales Order belongs to another Company. Change Operating Context before creating its Delivery Note."))
	if operating_branch and branch and operating_branch != branch:
		frappe.throw(_("The Sales Order Branch does not match the current Operating Branch."))
	return company, branch


def _validate_mapped_delivery_stock_context(target, *, company: str, source_branch: str) -> str:
	"""Validate every mapped Stock Location before the draft is inserted."""
	operating = get_operating_context() or {}
	operating_branch = str(operating.get("branch") or "").strip()
	resolved_branches: set[str] = set()

	for row in target.get("items") or []:
		warehouse = str(row.get("warehouse") or "").strip()
		if not warehouse:
			continue
		_assert_read("Warehouse", warehouse)
		warehouse_company = str(frappe.db.get_value("Warehouse", warehouse, "company") or "").strip()
		if warehouse_company and warehouse_company != company:
			frappe.throw(_("Stock Location {0} does not belong to Company {1}.").format(warehouse, company))
		resolved = resolve_branch_from_warehouse(warehouse, company=company)
		warehouse_branch = str(resolved.get("branch") or "").strip()
		if warehouse_branch:
			validate_user_branch_access(warehouse_branch, user=frappe.session.user, company=company, throw=True)
			resolved_branches.add(warehouse_branch)

	if len(resolved_branches) > 1:
		frappe.throw(_("The mapped Delivery Note spans Stock Locations from multiple Branches. Use the native Delivery Note workflow to split the delivery safely."))
	mapped_branch = next(iter(resolved_branches), "") or _source_branch(target) or source_branch
	if operating_branch and mapped_branch and operating_branch != mapped_branch:
		frappe.throw(_("The mapped Delivery Stock Location does not match the current Operating Branch."))
	return mapped_branch


@frappe.whitelist(methods=["POST"])
def create_delivery_note_from_sales_order(sales_order: str) -> dict[str, Any]:
	"""Create one draft Delivery Note from remaining quantities on a submitted Sales Order.

	ERPNext's native mapper owns quantity selection, item links, taxes, packed
	items and stock semantics. RetailEdge validates access/context and inserts the
	mapped draft only; it never changes or submits the source Sales Order.
	"""
	if not _permission("Delivery Note", "create"):
		frappe.throw(_("You do not have permission to create Delivery Note."), frappe.PermissionError)

	sales_order = str(sales_order or "").strip()
	_assert_read("Sales Order", sales_order)
	source = frappe.get_doc("Sales Order", sales_order)
	if source.docstatus != 1:
		frappe.throw(_("Submit the Sales Order before creating a Delivery Note from it."))
	if str(source.get("status") or "") in {"Closed", "Completed", "Cancelled"}:
		frappe.throw(_("This Sales Order is not open for delivery."))
	if str(source.get("delivery_status") or "") == "Fully Delivered":
		frappe.throw(_("This Sales Order is already fully delivered."))

	company, source_branch = _validate_source_against_operating_context(source)

	# ERPNext owns remaining-quantity checks, Sales Order Item -> Delivery Note Item
	# references, packed items, tax mapping and stock semantics.
	target = erpnext_make_delivery_note(source.name)
	if not target or target.doctype != "Delivery Note":
		frappe.throw(_("ERPNext could not prepare a Delivery Note from this Sales Order."))
	if target.docstatus != 0:
		frappe.throw(_("ERPNext returned a non-draft Delivery Note mapping; creation was stopped."))
	if not target.get("items"):
		frappe.throw(_("There are no remaining deliverable quantities on this Sales Order."))
	if str(target.get("company") or "") != company:
		frappe.throw(_("The mapped Delivery Note Company does not match the Sales Order."))

	mapped_branch = _validate_mapped_delivery_stock_context(target, company=company, source_branch=source_branch)
	if target.get("shipping_rule"):
		_validate_shipping_rule(target.shipping_rule, company=company)

	# Draft insertion only. No stock ledger entry is created until normal ERPNext
	# submission by an authorised user.
	target.insert()
	return {
		"doctype": target.doctype,
		"name": target.name,
		"docstatus": target.docstatus,
		"customer": target.customer,
		"company": target.company,
		"branch": target.get("branch") or target.get("retailedge_branch") or mapped_branch,
		"shipping_rule": target.get("shipping_rule") or "",
		"grand_total": target.grand_total,
		"currency": target.currency,
		"source_sales_order": source.name,
		"route": f"/app/delivery-note/{target.name}",
	}
