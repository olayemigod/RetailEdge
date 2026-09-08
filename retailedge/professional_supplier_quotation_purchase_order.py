from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.buying.doctype.supplier_quotation.supplier_quotation import make_purchase_order

from retailedge.branch_context import user_has_global_branch_access, validate_user_branch_access
from retailedge.professional_purchase_order import _assert_can_create_purchase_order, _set_branch
from retailedge.professional_purchasing import (
	PURCHASE_ORDER_DOCTYPE,
	REQUEST_FOR_QUOTATION_DOCTYPE,
	SUPPLIER_QUOTATION_DOCTYPE,
	_assert_read,
	_transaction_branch_field,
)

BLOCKED_SUPPLIER_QUOTATION_STATUSES = {"Cancelled", "Stopped", "Expired"}
PURCHASE_ORDER_ITEM_DOCTYPE = "Purchase Order Item"


def _get_submitted_supplier_quotation(name: str) -> Any:
	name = str(name or "").strip()
	if not name:
		frappe.throw(_("Supplier Quotation is required."))
	if not frappe.db.exists(SUPPLIER_QUOTATION_DOCTYPE, name):
		frappe.throw(_("Supplier Quotation {0} does not exist.").format(name))
	_assert_read(SUPPLIER_QUOTATION_DOCTYPE, name)
	doc = frappe.get_doc(SUPPLIER_QUOTATION_DOCTYPE, name)
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Only submitted Supplier Quotations can prepare a Purchase Order."))
	if str(getattr(doc, "status", "") or "") in BLOCKED_SUPPLIER_QUOTATION_STATUSES:
		frappe.throw(_("Supplier Quotation {0} is not available for Purchase Order conversion.").format(doc.name))
	return doc


def _linked_rfq_names(doc: Any) -> list[str]:
	return sorted(
		{
			str(getattr(row, "request_for_quotation", "") or "").strip()
			for row in (getattr(doc, "items", None) or [])
			if str(getattr(row, "request_for_quotation", "") or "").strip()
		}
	)


def _resolve_supplier_quotation_branch(doc: Any) -> str:
	"""Resolve one safe operating Branch for a quotation-to-PO conversion."""
	user = frappe.session.user
	global_access = user_has_global_branch_access(user=user)
	direct_branch_field = _transaction_branch_field(SUPPLIER_QUOTATION_DOCTYPE)
	direct_branch = str(getattr(doc, direct_branch_field, "") or "").strip() if direct_branch_field else ""
	if direct_branch:
		validate_user_branch_access(direct_branch, user=user, company=doc.company, throw=True)
	elif direct_branch_field and not global_access:
		frappe.throw(
			_("Supplier Quotation {0} has no Branch attribution for your restricted access.").format(doc.name),
			frappe.PermissionError,
		)

	rfq_names = _linked_rfq_names(doc)
	linked_branches: set[str] = set()
	for rfq_name in rfq_names:
		_assert_read(REQUEST_FOR_QUOTATION_DOCTYPE, rfq_name)
		rfq = frappe.get_doc(REQUEST_FOR_QUOTATION_DOCTYPE, rfq_name)
		if str(getattr(rfq, "company", "") or "") != str(doc.company or ""):
			frappe.throw(_("Linked Request for Quotation {0} belongs to a different Company.").format(rfq_name))
		rfq_branch_field = _transaction_branch_field(REQUEST_FOR_QUOTATION_DOCTYPE)
		branch = str(getattr(rfq, rfq_branch_field, "") or "").strip() if rfq_branch_field else ""
		if branch:
			validate_user_branch_access(branch, user=user, company=doc.company, throw=True)
			linked_branches.add(branch)
		elif not global_access:
			frappe.throw(
				_("Linked Request for Quotation {0} has no Branch attribution for your restricted access.").format(rfq_name),
				frappe.PermissionError,
			)

	if len(linked_branches) > 1:
		frappe.throw(_("Supplier Quotation {0} spans multiple Branches and requires Advanced ERPNext review.").format(doc.name))
	linked_branch = next(iter(linked_branches), "")
	if direct_branch and linked_branch and direct_branch != linked_branch:
		frappe.throw(_("Supplier Quotation Branch does not match its linked Request for Quotation Branch."))
	branch = direct_branch or linked_branch
	if not branch and not global_access:
		frappe.throw(
			_("Supplier Quotation {0} is not attributable to a permitted Branch. Use an authorised manager to correct the sourcing chain.").format(doc.name),
			frappe.PermissionError,
		)
	return branch


def _mapped_purchase_order(doc: Any, branch: str) -> tuple[Any, list[dict[str, Any]]]:
	purchase_order = make_purchase_order(doc.name)
	if not purchase_order or getattr(purchase_order, "doctype", None) != PURCHASE_ORDER_DOCTYPE:
		frappe.throw(_("ERPNext could not map Supplier Quotation {0} to a Purchase Order.").format(doc.name))
	if str(getattr(purchase_order, "company", "") or "") != str(doc.company or ""):
		frappe.throw(_("Mapped Purchase Order Company does not match the Supplier Quotation."))
	if str(getattr(purchase_order, "supplier", "") or "") != str(doc.supplier or ""):
		frappe.throw(_("Mapped Purchase Order Supplier does not match the Supplier Quotation."))
	if branch:
		_set_branch(purchase_order, branch)

	items: list[dict[str, Any]] = []
	for row in getattr(purchase_order, "items", None) or []:
		if flt(getattr(row, "qty", 0)) <= 0:
			continue
		if str(getattr(row, "supplier_quotation", "") or "") != doc.name:
			frappe.throw(_("Mapped Purchase Order contains an item outside Supplier Quotation {0}.").format(doc.name))
		items.append(
			{
				"item_code": str(getattr(row, "item_code", "") or ""),
				"item_name": str(getattr(row, "item_name", "") or getattr(row, "item_code", "") or ""),
				"qty": flt(getattr(row, "qty", 0)),
				"uom": str(getattr(row, "uom", "") or ""),
				"rate": flt(getattr(row, "rate", 0)),
				"amount": flt(getattr(row, "amount", 0)),
				"schedule_date": str(getattr(row, "schedule_date", "") or ""),
				"warehouse": str(getattr(row, "warehouse", "") or ""),
				"supplier_quotation_item": str(getattr(row, "supplier_quotation_item", "") or ""),
			}
		)
	if not items:
		frappe.throw(_("Supplier Quotation {0} has no items available for Purchase Order conversion.").format(doc.name))
	return purchase_order, items


def _existing_active_purchase_order(supplier_quotation: str) -> str:
	rows = frappe.get_all(
		PURCHASE_ORDER_ITEM_DOCTYPE,
		filters={"supplier_quotation": supplier_quotation, "docstatus": ["<", 2]},
		pluck="parent",
		limit_page_length=20,
	)
	return str(rows[0] or "") if rows else ""


@frappe.whitelist()
def get_supplier_quotation_purchase_order_preview(supplier_quotation: str) -> dict[str, Any]:
	"""Preview ERPNext's Supplier Quotation -> Purchase Order mapping without saving."""
	doc = _get_submitted_supplier_quotation(supplier_quotation)
	_assert_can_create_purchase_order()
	branch = _resolve_supplier_quotation_branch(doc)
	purchase_order, items = _mapped_purchase_order(doc, branch)
	existing = _existing_active_purchase_order(doc.name)

	return {
		"supplier_quotation": doc.name,
		"supplier_quotation_modified": str(getattr(doc, "modified", "") or ""),
		"company": str(doc.company or ""),
		"branch": branch,
		"supplier": str(doc.supplier or ""),
		"supplier_name": str(getattr(doc, "supplier_name", "") or doc.supplier or ""),
		"currency": str(getattr(purchase_order, "currency", "") or getattr(doc, "currency", "") or ""),
		"grand_total": flt(getattr(purchase_order, "grand_total", 0)),
		"total_qty": flt(getattr(purchase_order, "total_qty", 0)),
		"item_count": len(items),
		"tax_row_count": len(getattr(purchase_order, "taxes", None) or []),
		"items": items,
		"existing_purchase_order": existing,
		"can_create_draft": not bool(existing),
		"persistence": "none",
		"status": "Preview only",
		"source_of_truth": "ERPNext Supplier Quotation make_purchase_order mapper",
	}


@frappe.whitelist(methods=["POST"])
def create_purchase_order_draft_from_supplier_quotation(
	supplier_quotation: str,
	expected_supplier_quotation_modified: str | None = None,
) -> dict[str, Any]:
	"""Create one ERPNext Purchase Order draft from a submitted Supplier Quotation mapping."""
	supplier_quotation = str(supplier_quotation or "").strip()
	if not supplier_quotation:
		frappe.throw(_("Supplier Quotation is required."))
	if not frappe.db.exists(SUPPLIER_QUOTATION_DOCTYPE, supplier_quotation):
		frappe.throw(_("Supplier Quotation {0} does not exist.").format(supplier_quotation))
	_assert_read(SUPPLIER_QUOTATION_DOCTYPE, supplier_quotation)

	frappe.db.sql(
		"SELECT name FROM `tabSupplier Quotation` WHERE name = %s FOR UPDATE",
		(supplier_quotation,),
	)
	doc = _get_submitted_supplier_quotation(supplier_quotation)
	_assert_can_create_purchase_order()

	expected_modified = str(expected_supplier_quotation_modified or "").strip()
	current_modified = str(getattr(doc, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(_("Supplier Quotation {0} changed after the preview. Refresh before creating the Purchase Order.").format(doc.name))

	existing = _existing_active_purchase_order(doc.name)
	if existing:
		frappe.throw(
			_("Purchase Order {0} already references Supplier Quotation {1}. Review the existing order instead of creating a duplicate.").format(existing, doc.name)
		)

	branch = _resolve_supplier_quotation_branch(doc)
	purchase_order, items = _mapped_purchase_order(doc, branch)
	purchase_order.insert()
	if cint(getattr(purchase_order, "docstatus", 0)) != 0:
		frappe.throw(_("Supplier Quotation conversion may create only a draft Purchase Order."))
	branch_field = _transaction_branch_field(PURCHASE_ORDER_DOCTYPE)

	return {
		"doctype": PURCHASE_ORDER_DOCTYPE,
		"name": purchase_order.name,
		"docstatus": cint(purchase_order.docstatus),
		"supplier_quotation": doc.name,
		"company": str(purchase_order.company or ""),
		"branch": str(getattr(purchase_order, branch_field, "") or "") if branch_field else "",
		"supplier": str(purchase_order.supplier or ""),
		"currency": str(getattr(purchase_order, "currency", "") or ""),
		"grand_total": flt(getattr(purchase_order, "grand_total", 0)),
		"item_count": len(items),
		"posting_status": "Draft",
		"source_of_truth": "ERPNext Supplier Quotation make_purchase_order mapper",
	}
