from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

from retailedge.branch_context import validate_user_branch_access
from retailedge.professional_purchasing import (
	PURCHASE_ORDER_DOCTYPE,
	_assert_read,
	_document_branch,
	_resolve_scope,
)

PURCHASE_RECEIPT_DOCTYPE = "Purchase Receipt"
CLOSED_PURCHASE_ORDER_STATUSES = {"Closed", "Completed", "Cancelled", "Stopped"}


def _item_flags(item_code: str) -> dict[str, bool]:
	if not item_code:
		return {"has_serial_no": False, "has_batch_no": False, "inspection_required": False}
	values = frappe.db.get_value(
		"Item",
		item_code,
		["has_serial_no", "has_batch_no", "inspection_required_before_purchase"],
		as_dict=True,
	) or {}
	return {
		"has_serial_no": bool(cint(values.get("has_serial_no"))),
		"has_batch_no": bool(cint(values.get("has_batch_no"))),
		"inspection_required": bool(cint(values.get("inspection_required_before_purchase"))),
	}


def _receipt_item_preview(row: Any) -> tuple[dict[str, Any], list[dict[str, str]]]:
	item_code = str(getattr(row, "item_code", None) or "").strip()
	flags = _item_flags(item_code)
	blockers: list[dict[str, str]] = []
	if flags["has_serial_no"]:
		blockers.append({"key": "serial_number", "label": _("Serial Number handling required"), "item_code": item_code})
	if flags["has_batch_no"]:
		blockers.append({"key": "batch", "label": _("Batch handling required"), "item_code": item_code})
	if flags["inspection_required"]:
		blockers.append({"key": "quality_inspection", "label": _("Quality Inspection required"), "item_code": item_code})
	if flt(getattr(row, "rejected_qty", 0)) > 0:
		blockers.append({"key": "rejected_quantity", "label": _("Rejected quantity requires advanced review"), "item_code": item_code})

	return (
		{
			"name": str(getattr(row, "name", None) or ""),
			"purchase_order": str(getattr(row, "purchase_order", None) or ""),
			"purchase_order_item": str(getattr(row, "purchase_order_item", None) or ""),
			"item_code": item_code,
			"item_name": str(getattr(row, "item_name", None) or item_code),
			"qty": flt(getattr(row, "qty", 0)),
			"received_qty": flt(getattr(row, "received_qty", 0)),
			"rejected_qty": flt(getattr(row, "rejected_qty", 0)),
			"uom": str(getattr(row, "uom", None) or ""),
			"stock_uom": str(getattr(row, "stock_uom", None) or ""),
			"warehouse": str(getattr(row, "warehouse", None) or ""),
			"rejected_warehouse": str(getattr(row, "rejected_warehouse", None) or ""),
			"requires_serial_no": flags["has_serial_no"],
			"requires_batch": flags["has_batch_no"],
			"requires_quality_inspection": flags["inspection_required"],
		},
		blockers,
	)


def _validate_po_scope(po: Any) -> str:
	branch = _document_branch(po)
	_company, _requested_branch, allowed_branches, global_access = _resolve_scope(
		company=str(po.company or ""),
		branch=branch or None,
	)
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=po.company, throw=True)
	elif not global_access:
		# A restricted user must never use a named-document preview to bypass the
		# Branch Assignment contract. Blank attribution cannot prove that this PO
		# belongs to one of the user's permitted branches.
		frappe.throw(
			_("Purchase Order {0} has no Branch attribution for your restricted access. Ask an authorised manager to correct the document before receiving it.").format(po.name),
			frappe.PermissionError,
		)
	if branch and allowed_branches and not global_access and branch not in allowed_branches:
		frappe.throw(_("You do not have access to Branch {0}.").format(branch), frappe.PermissionError)
	return branch


@frappe.whitelist()
def get_professional_purchase_receipt_preview(purchase_order: str) -> dict[str, Any]:
	"""Preview ERPNext's standard PO -> Purchase Receipt mapping without saving anything."""
	purchase_order = str(purchase_order or "").strip()
	if not purchase_order:
		frappe.throw(_("Purchase Order is required."))
	if not frappe.db.exists(PURCHASE_ORDER_DOCTYPE, purchase_order):
		frappe.throw(_("Purchase Order {0} does not exist.").format(purchase_order))
	_assert_read(PURCHASE_ORDER_DOCTYPE, purchase_order)

	po = frappe.get_doc(PURCHASE_ORDER_DOCTYPE, purchase_order)
	if cint(po.docstatus) != 1:
		frappe.throw(_("Only a submitted Purchase Order can be previewed for receipt."))
	if str(getattr(po, "status", "") or "") in CLOSED_PURCHASE_ORDER_STATUSES:
		frappe.throw(_("Purchase Order {0} is not open for receiving.").format(purchase_order))
	if flt(getattr(po, "per_received", 0)) >= 100:
		frappe.throw(_("Purchase Order {0} is already fully received.").format(purchase_order))
	if not frappe.has_permission(PURCHASE_RECEIPT_DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Purchase Receipt."), frappe.PermissionError)

	branch = _validate_po_scope(po)

	# ERPNext performs the authoritative Purchase Order -> Purchase Receipt mapping.
	# The mapped document stays in memory only. RIR2F2D1 must not insert, save,
	# submit, or otherwise post stock/accounting state.
	receipt = make_purchase_receipt(po.name)
	if not receipt or getattr(receipt, "doctype", None) != PURCHASE_RECEIPT_DOCTYPE:
		frappe.throw(_("ERPNext could not preview a Purchase Receipt from {0}.").format(purchase_order))
	if str(getattr(receipt, "company", "") or "") != str(po.company or ""):
		frappe.throw(_("Mapped Purchase Receipt Company does not match the Purchase Order."))
	if str(getattr(receipt, "supplier", "") or "") != str(po.supplier or ""):
		frappe.throw(_("Mapped Purchase Receipt Supplier does not match the Purchase Order."))

	items: list[dict[str, Any]] = []
	blockers: list[dict[str, str]] = []
	if cint(getattr(po, "is_subcontracted", 0)):
		blockers.append({"key": "subcontracting", "label": _("Subcontracted Purchase Order requires Advanced ERPNext")})

	for row in receipt.items or []:
		if flt(getattr(row, "qty", 0)) <= 0:
			continue
		if str(getattr(row, "purchase_order", "") or "") != po.name:
			frappe.throw(_("Mapped Purchase Receipt contains an item outside Purchase Order {0}.").format(po.name))
		preview, row_blockers = _receipt_item_preview(row)
		items.append(preview)
		blockers.extend(row_blockers)

	if not items:
		blockers.append({"key": "no_receivable_items", "label": _("No receivable quantity remains on this Purchase Order")})

	return {
		"purchase_order": po.name,
		"company": str(po.company or ""),
		"branch": branch,
		"supplier": str(po.supplier or ""),
		"supplier_name": str(getattr(po, "supplier_name", None) or po.supplier or ""),
		"posting_date": str(getattr(receipt, "posting_date", None) or ""),
		"items": items,
		"blockers": blockers,
		"standard_receipt_eligible": not blockers,
		"persistence": "none",
		"posting_status": "Preview only",
		"source_of_truth": "ERPNext Purchase Receipt mapper",
		"next_phase": "RIR2F2D2",
	}
