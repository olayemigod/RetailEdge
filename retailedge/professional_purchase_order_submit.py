from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.branch_context import user_has_global_branch_access, validate_user_branch_access
from retailedge.professional_purchasing import (
	PURCHASE_ORDER_DOCTYPE,
	_assert_read,
	_document_branch,
	_permission,
)

BLOCKED_DRAFT_STATUSES = {"On Hold", "Closed", "Cancelled"}


def _active_purchase_order_workflow() -> str:
	return str(
		frappe.db.get_value(
			"Workflow",
			{"document_type": PURCHASE_ORDER_DOCTYPE, "is_active": 1},
			"name",
		)
		or ""
	)


def _get_purchase_order(name: str) -> Any:
	name = str(name or "").strip()
	if not name:
		frappe.throw(_("Purchase Order is required."))
	if not frappe.db.exists(PURCHASE_ORDER_DOCTYPE, name):
		frappe.throw(_("Purchase Order {0} does not exist.").format(name))
	_assert_read(PURCHASE_ORDER_DOCTYPE, name)
	return frappe.get_doc(PURCHASE_ORDER_DOCTYPE, name)


def _validate_purchase_order_branch(doc: Any) -> str:
	branch = _document_branch(doc)
	global_access = user_has_global_branch_access(user=frappe.session.user)
	if branch:
		validate_user_branch_access(
			branch,
			user=frappe.session.user,
			company=doc.company,
			throw=True,
		)
	elif not global_access:
		frappe.throw(
			_("Purchase Order {0} has no Branch attribution for your restricted access.").format(doc.name),
			frappe.PermissionError,
		)
	return branch


def _standard_submit_blockers(doc: Any) -> list[str]:
	blockers: list[str] = []
	if cint(doc.docstatus) != 0:
		blockers.append(_("Only draft Purchase Orders can use standard EdgeSuite submission."))
	status = str(getattr(doc, "status", "") or "")
	if status in BLOCKED_DRAFT_STATUSES:
		blockers.append(_("Purchase Order status {0} requires Advanced ERPNext review.").format(status))
	if cint(getattr(doc, "is_subcontracted", 0)) or cint(getattr(doc, "is_old_subcontracting_flow", 0)):
		blockers.append(_("Subcontracting Purchase Orders require Advanced ERPNext review."))
	if cint(getattr(doc, "is_internal_supplier", 0)) or str(getattr(doc, "inter_company_order_reference", "") or ""):
		blockers.append(_("Inter-company Purchase Orders require Advanced ERPNext review."))
	workflow = _active_purchase_order_workflow()
	if workflow:
		blockers.append(
			_("Purchase Order approval Workflow {0} is active. Use the workflow-aware ERPNext approval path.").format(workflow)
		)
	if not _permission(PURCHASE_ORDER_DOCTYPE, "submit", doc.name):
		blockers.append(_("You do not have permission to submit this Purchase Order."))
	return blockers


def _item_preview(doc: Any) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	for row in getattr(doc, "items", None) or []:
		qty = flt(getattr(row, "qty", 0))
		if qty <= 0:
			continue
		items.append(
			{
				"item_code": str(getattr(row, "item_code", "") or ""),
				"item_name": str(getattr(row, "item_name", "") or getattr(row, "item_code", "") or ""),
				"qty": qty,
				"uom": str(getattr(row, "uom", "") or ""),
				"rate": flt(getattr(row, "rate", 0)),
				"amount": flt(getattr(row, "amount", 0)),
				"schedule_date": str(getattr(row, "schedule_date", "") or ""),
				"warehouse": str(getattr(row, "warehouse", "") or ""),
			}
		)
	if not items:
		frappe.throw(_("Purchase Order {0} has no positive-quantity items to submit.").format(doc.name))
	return items


@frappe.whitelist()
def get_purchase_order_submit_preview(purchase_order: str) -> dict[str, Any]:
	"""Review one draft PO before standard ERPNext submission; no writes occur."""
	doc = _get_purchase_order(purchase_order)
	branch = _validate_purchase_order_branch(doc)
	items = _item_preview(doc)
	blockers = _standard_submit_blockers(doc)

	return {
		"purchase_order": doc.name,
		"purchase_order_modified": str(getattr(doc, "modified", "") or ""),
		"company": str(getattr(doc, "company", "") or ""),
		"branch": branch,
		"supplier": str(getattr(doc, "supplier", "") or ""),
		"supplier_name": str(getattr(doc, "supplier_name", "") or getattr(doc, "supplier", "") or ""),
		"currency": str(getattr(doc, "currency", "") or ""),
		"grand_total": flt(getattr(doc, "grand_total", 0)),
		"total_qty": flt(getattr(doc, "total_qty", 0)),
		"item_count": len(items),
		"tax_row_count": len(getattr(doc, "taxes", None) or []),
		"items": items,
		"blockers": blockers,
		"can_submit": not blockers,
		"persistence": "none",
		"status": "Review only",
		"source_of_truth": "ERPNext Purchase Order",
	}


@frappe.whitelist(methods=["POST"])
def submit_standard_purchase_order(
	purchase_order: str,
	expected_purchase_order_modified: str | None = None,
) -> dict[str, Any]:
	"""Submit one standard PO through ERPNext after fresh permission/scope checks."""
	purchase_order = str(purchase_order or "").strip()
	if not purchase_order:
		frappe.throw(_("Purchase Order is required."))
	if not frappe.db.exists(PURCHASE_ORDER_DOCTYPE, purchase_order):
		frappe.throw(_("Purchase Order {0} does not exist.").format(purchase_order))
	_assert_read(PURCHASE_ORDER_DOCTYPE, purchase_order)

	frappe.db.sql(
		"SELECT name FROM `tabPurchase Order` WHERE name = %s FOR UPDATE",
		(purchase_order,),
	)
	doc = _get_purchase_order(purchase_order)
	branch = _validate_purchase_order_branch(doc)
	_item_preview(doc)

	expected_modified = str(expected_purchase_order_modified or "").strip()
	current_modified = str(getattr(doc, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(_("Purchase Order {0} changed after the review. Refresh before submitting.").format(doc.name))

	blockers = _standard_submit_blockers(doc)
	if blockers:
		frappe.throw("<br>".join(blockers))

	# ERPNext remains authoritative for Purchase Order submission side effects,
	# including ordered-quantity/status updates on linked procurement documents.
	doc.submit()
	if cint(getattr(doc, "docstatus", 0)) != 1:
		frappe.throw(_("ERPNext did not submit Purchase Order {0}.").format(doc.name))

	return {
		"doctype": PURCHASE_ORDER_DOCTYPE,
		"name": doc.name,
		"docstatus": cint(doc.docstatus),
		"company": str(getattr(doc, "company", "") or ""),
		"branch": branch,
		"supplier": str(getattr(doc, "supplier", "") or ""),
		"currency": str(getattr(doc, "currency", "") or ""),
		"grand_total": flt(getattr(doc, "grand_total", 0)),
		"status": str(getattr(doc, "status", "") or "Submitted"),
		"source_of_truth": "ERPNext Purchase Order submit",
	}
