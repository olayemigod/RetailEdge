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
	_branch_scoped_filters,
	_document_branch,
	_resolve_scope,
	_transaction_branch_field,
)

PURCHASE_RECEIPT_DOCTYPE = "Purchase Receipt"
CLOSED_PURCHASE_ORDER_STATUSES = {"Closed", "Completed", "Cancelled", "Stopped"}
MAX_RECEIPT_HISTORY = 100


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
		frappe.throw(
			_("Purchase Order {0} has no Branch attribution for your restricted access. Ask an authorised manager to correct the document before receiving it.").format(po.name),
			frappe.PermissionError,
		)
	if branch and allowed_branches and not global_access and branch not in allowed_branches:
		frappe.throw(_("You do not have access to Branch {0}.").format(branch), frappe.PermissionError)
	return branch


def _validate_open_po(po: Any) -> None:
	if cint(po.docstatus) != 1:
		frappe.throw(_("Only a submitted Purchase Order can be received."))
	if str(getattr(po, "status", "") or "") in CLOSED_PURCHASE_ORDER_STATUSES:
		frappe.throw(_("Purchase Order {0} is not open for receiving.").format(po.name))
	if flt(getattr(po, "per_received", 0)) >= 100:
		frappe.throw(_("Purchase Order {0} is already fully received.").format(po.name))


def _assert_receipt_permissions(*, require_submit: bool = False) -> None:
	if not frappe.has_permission(PURCHASE_RECEIPT_DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Purchase Receipt."), frappe.PermissionError)
	if require_submit and not frappe.has_permission(PURCHASE_RECEIPT_DOCTYPE, "submit"):
		frappe.throw(_("You do not have permission to submit Purchase Receipt."), frappe.PermissionError)


def _map_receipt(po: Any, branch: str) -> tuple[Any, list[dict[str, Any]], list[dict[str, str]]]:
	receipt = make_purchase_receipt(po.name)
	if not receipt or getattr(receipt, "doctype", None) != PURCHASE_RECEIPT_DOCTYPE:
		frappe.throw(_("ERPNext could not prepare a Purchase Receipt from {0}.").format(po.name))
	if str(getattr(receipt, "company", "") or "") != str(po.company or ""):
		frappe.throw(_("Mapped Purchase Receipt Company does not match the Purchase Order."))
	if str(getattr(receipt, "supplier", "") or "") != str(po.supplier or ""):
		frappe.throw(_("Mapped Purchase Receipt Supplier does not match the Purchase Order."))

	receipt_branch_field = _transaction_branch_field(PURCHASE_RECEIPT_DOCTYPE)
	if branch and receipt_branch_field:
		setattr(receipt, receipt_branch_field, branch)
	elif branch and not receipt_branch_field:
		frappe.throw(_("Purchase Receipt branch attribution is unavailable. Run site migration before receiving for this Branch."))

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
		warehouse = str(preview.get("warehouse") or "").strip()
		if not warehouse:
			row_blockers.append({"key": "missing_warehouse", "label": _("Receiving Stock Location is required"), "item_code": preview.get("item_code") or ""})
		else:
			warehouse_company = str(frappe.db.get_value("Warehouse", warehouse, "company") or "")
			if warehouse_company != str(po.company or ""):
				frappe.throw(_("Receiving Stock Location {0} does not belong to Company {1}.").format(warehouse, po.company))
		items.append(preview)
		blockers.extend(row_blockers)

	if not items:
		blockers.append({"key": "no_receivable_items", "label": _("No receivable quantity remains on this Purchase Order")})
	return receipt, items, blockers


def _get_purchase_order_for_receipt(purchase_order: str, *, lock: bool = False) -> Any:
	purchase_order = str(purchase_order or "").strip()
	if not purchase_order:
		frappe.throw(_("Purchase Order is required."))
	if not frappe.db.exists(PURCHASE_ORDER_DOCTYPE, purchase_order):
		frappe.throw(_("Purchase Order {0} does not exist.").format(purchase_order))
	_assert_read(PURCHASE_ORDER_DOCTYPE, purchase_order)
	if lock:
		# Serialize standard receipt posting for one Purchase Order. This prevents
		# double-click/concurrent requests from mapping the same remaining quantity.
		frappe.db.sql(
			"SELECT name FROM `tabPurchase Order` WHERE name = %s FOR UPDATE",
			(purchase_order,),
		)
	return frappe.get_doc(PURCHASE_ORDER_DOCTYPE, purchase_order)


@frappe.whitelist()
def get_professional_purchase_receipt_preview(purchase_order: str) -> dict[str, Any]:
	"""Preview ERPNext's standard PO -> Purchase Receipt mapping without saving anything."""
	po = _get_purchase_order_for_receipt(purchase_order)
	_validate_open_po(po)
	_assert_receipt_permissions()
	branch = _validate_po_scope(po)
	receipt, items, blockers = _map_receipt(po, branch)

	return {
		"purchase_order": po.name,
		"purchase_order_modified": str(getattr(po, "modified", None) or ""),
		"company": str(po.company or ""),
		"branch": branch,
		"supplier": str(po.supplier or ""),
		"supplier_name": str(getattr(po, "supplier_name", None) or po.supplier or ""),
		"posting_date": str(getattr(receipt, "posting_date", None) or ""),
		"items": items,
		"blockers": blockers,
		"standard_receipt_eligible": not blockers,
		"can_submit": bool(not blockers and frappe.has_permission(PURCHASE_RECEIPT_DOCTYPE, "submit")),
		"persistence": "none",
		"posting_status": "Preview only",
		"source_of_truth": "ERPNext Purchase Receipt mapper",
		"next_phase": "RIR2F2D2 standard receipt posting",
	}


@frappe.whitelist(methods=["POST"])
def submit_standard_purchase_receipt(
	purchase_order: str,
	expected_purchase_order_modified: str | None = None,
) -> dict[str, Any]:
	"""Insert and submit one standard ERPNext Purchase Receipt after a fresh server-side preflight."""
	po = _get_purchase_order_for_receipt(purchase_order, lock=True)
	_validate_open_po(po)
	_assert_receipt_permissions(require_submit=True)

	expected_modified = str(expected_purchase_order_modified or "").strip()
	current_modified = str(getattr(po, "modified", None) or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(_("Purchase Order {0} changed after the receipt preview. Refresh the preview before posting.").format(po.name))

	branch = _validate_po_scope(po)
	receipt, items, blockers = _map_receipt(po, branch)
	if blockers:
		labels = ", ".join(str(blocker.get("label") or blocker.get("key") or "") for blocker in blockers)
		frappe.throw(_("This Purchase Receipt requires Advanced ERPNext handling: {0}").format(labels))

	# ERPNext remains authoritative for receipt validation and stock posting.
	# Insert and submit run as the current user; no ignore_permissions or direct
	# Stock Ledger / GL Entry writes are allowed in this EdgeSuite path.
	receipt.insert()
	receipt.submit()
	if cint(getattr(receipt, "docstatus", 0)) != 1:
		frappe.throw(_("ERPNext did not submit Purchase Receipt {0}.").format(receipt.name))

	receipt_branch_field = _transaction_branch_field(PURCHASE_RECEIPT_DOCTYPE)
	return {
		"doctype": PURCHASE_RECEIPT_DOCTYPE,
		"name": receipt.name,
		"docstatus": cint(receipt.docstatus),
		"purchase_order": po.name,
		"company": str(receipt.company or ""),
		"supplier": str(receipt.supplier or ""),
		"branch": str(getattr(receipt, receipt_branch_field, "") or "") if receipt_branch_field else "",
		"item_count": len(items),
		"posting_status": "Submitted",
		"stock_posted_by": "ERPNext Purchase Receipt submit",
		"source_of_truth": "ERPNext Purchase Order make_purchase_receipt mapper",
	}


@frappe.whitelist()
def get_professional_purchase_receipt_history(
	company: str | None = None,
	branch: str | None = None,
	supplier: str | None = None,
	limit: int | str = 50,
) -> dict[str, Any]:
	"""Return a bounded, permission-aware list of submitted non-return Purchase Receipts."""
	_assert_read(PURCHASE_RECEIPT_DOCTYPE)
	company, branch, allowed_branches, global_branch_access = _resolve_scope(company, branch)
	supplier = str(supplier or "").strip()
	if supplier:
		_assert_read("Supplier", supplier)

	filters, branch_field = _branch_scoped_filters(
		PURCHASE_RECEIPT_DOCTYPE,
		company=company,
		branch=branch,
		allowed_branches=allowed_branches,
		global_branch_access=global_branch_access,
	)
	filters.update({"docstatus": 1, "is_return": 0})
	if supplier:
		filters["supplier"] = supplier
	row_limit = max(1, min(cint(limit) or 50, MAX_RECEIPT_HISTORY))
	fields = [
		"name",
		"posting_date",
		"posting_time",
		"company",
		"supplier",
		"supplier_name",
		"status",
		"total_qty",
		"modified",
	]
	if branch_field:
		fields.append(branch_field)

	rows = frappe.get_list(
		PURCHASE_RECEIPT_DOCTYPE,
		filters=filters,
		fields=fields,
		order_by="posting_date desc, posting_time desc, name desc",
		limit_page_length=row_limit,
	)
	names = [str(row.get("name") or "") for row in rows if row.get("name")]
	purchase_orders: dict[str, list[str]] = {name: [] for name in names}
	if names:
		for item in frappe.get_all(
			"Purchase Receipt Item",
			filters={"parent": ["in", names]},
			fields=["parent", "purchase_order"],
		):
			parent = str(item.get("parent") or "")
			purchase_order = str(item.get("purchase_order") or "")
			if parent in purchase_orders and purchase_order and purchase_order not in purchase_orders[parent]:
				purchase_orders[parent].append(purchase_order)

	return {
		"company": company,
		"branch": branch,
		"supplier": supplier,
		"limit": row_limit,
		"receipts": [
			{
				"name": str(row.get("name") or ""),
				"posting_date": row.get("posting_date"),
				"posting_time": row.get("posting_time"),
				"company": str(row.get("company") or ""),
				"branch": str(row.get(branch_field) or "") if branch_field else "",
				"supplier": str(row.get("supplier") or ""),
				"supplier_name": str(row.get("supplier_name") or row.get("supplier") or ""),
				"status": str(row.get("status") or "Submitted"),
				"total_qty": flt(row.get("total_qty")),
				"purchase_orders": purchase_orders.get(str(row.get("name") or ""), []),
			}
			for row in rows
		],
		"source_of_truth": "ERPNext Purchase Receipt",
	}
