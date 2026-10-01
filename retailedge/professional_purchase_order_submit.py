from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt, getdate

from retailedge.guided_pricing import resolve_purchase_item_pricing
from retailedge.guided_purchase_invoice import MAX_ITEMS
from retailedge.operating_context import get_operational_branch_scope, validate_operating_branch
from retailedge.professional_purchasing import (
	PURCHASE_ORDER_DOCTYPE,
	_assert_read,
	_document_branch,
	_permission,
)
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_workflow_readiness

BLOCKED_DRAFT_STATUSES = {"On Hold", "Closed", "Cancelled"}

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
	company = str(getattr(doc, "company", "") or "").strip()
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	if branch:
		validate_operating_branch(
			company=company,
			branch=branch,
			user=frappe.session.user,
			throw=True,
		)
		if scope.get("restricted") and branch not in (scope.get("allowed_branches") or []):
			frappe.throw(
				_("You do not have active operational access to Branch {0}.").format(branch),
				frappe.PermissionError,
			)
	elif scope.get("restricted"):
		frappe.throw(
			_("Purchase Order {0} has no Branch attribution for your restricted access.").format(doc.name),
			frappe.PermissionError,
		)
	return branch


def _workflow_submit_blocker(workflow_readiness: dict[str, Any]) -> str:
	if str(workflow_readiness.get("source") or "") != "frappe":
		return ""
	return _(
		"Purchase Order is controlled by active Workflow {0}. Use the available workflow action in EdgeSuite."
	).format(workflow_readiness.get("workflow") or _("Purchase Order Workflow"))


def _standard_submit_blockers(
	doc: Any,
	workflow_readiness: dict[str, Any] | None = None,
) -> list[str]:
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
	workflow_readiness = workflow_readiness or get_workflow_readiness(
		doctype=PURCHASE_ORDER_DOCTYPE,
		doc=doc,
	)
	workflow_blocker = _workflow_submit_blocker(workflow_readiness)
	if workflow_blocker:
		blockers.append(workflow_blocker)
	elif not _permission(PURCHASE_ORDER_DOCTYPE, "submit", doc.name):
		blockers.append(_("You do not have permission to submit this Purchase Order."))
	return blockers


def _submitted_next_actions(doc: Any) -> list[dict[str, str]]:
	if cint(getattr(doc, "docstatus", 0)) != 1:
		return []
	status = str(getattr(doc, "status", "") or "").strip()
	if status in {"Closed", "Completed", "Cancelled", "Stopped"}:
		return []
	if cint(getattr(doc, "is_subcontracted", 0)) or cint(getattr(doc, "is_old_subcontracting_flow", 0)):
		return []

	actions: list[dict[str, str]] = []
	if _permission("Purchase Receipt", "create") and flt(getattr(doc, "per_received", 0)) < 99.999:
		actions.append({"value": "receive-stock", "label": _("Receive Stock")})
	if _permission("Purchase Invoice", "create") and flt(getattr(doc, "per_billed", 0)) < 99.999:
		actions.append({"value": "create-purchase-invoice", "label": _("Create Purchase Invoice")})
	return actions


def _item_preview(doc: Any) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	for row in getattr(doc, "items", None) or []:
		qty = flt(getattr(row, "qty", 0))
		if qty <= 0:
			continue
		items.append(
			{
				"name": str(getattr(row, "name", "") or ""),
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


def _build_preview(doc: Any) -> dict[str, Any]:
	branch = _validate_purchase_order_branch(doc)
	items = _item_preview(doc)
	workflow_readiness = get_workflow_readiness(
		doctype=PURCHASE_ORDER_DOCTYPE,
		doc=doc,
	)
	blockers = _standard_submit_blockers(
		doc,
		workflow_readiness=workflow_readiness,
	)
	workflow_blocker = _workflow_submit_blocker(workflow_readiness)
	workflow_eligible = bool(
		workflow_blocker
		and not [blocker for blocker in blockers if blocker != workflow_blocker]
	)

	return {
		"purchase_order": doc.name,
		"purchase_order_modified": str(getattr(doc, "modified", "") or ""),
		"company": str(getattr(doc, "company", "") or ""),
		"branch": branch,
		"supplier": str(getattr(doc, "supplier", "") or ""),
		"supplier_name": str(getattr(doc, "supplier_name", "") or getattr(doc, "supplier", "") or ""),
		"currency": str(getattr(doc, "currency", "") or ""),
		"buying_price_list": str(getattr(doc, "buying_price_list", "") or ""),
		"default_warehouse": str(getattr(doc, "set_warehouse", "") or ""),
		"transaction_date": str(getattr(doc, "transaction_date", "") or ""),
		"schedule_date": str(getattr(doc, "schedule_date", "") or ""),
		"terms": str(getattr(doc, "terms", "") or ""),
		"grand_total": flt(getattr(doc, "grand_total", 0)),
		"total_qty": flt(getattr(doc, "total_qty", 0)),
		"item_count": len(items),
		"tax_row_count": len(getattr(doc, "taxes", None) or []),
		"items": items,
		"blockers": blockers,
		"can_edit": bool(
			cint(getattr(doc, "docstatus", 0)) == 0
			and str(getattr(doc, "status", "") or "") not in BLOCKED_DRAFT_STATUSES
			and not cint(getattr(doc, "is_subcontracted", 0))
			and not cint(getattr(doc, "is_old_subcontracting_flow", 0))
			and not cint(getattr(doc, "is_internal_supplier", 0))
			and not str(getattr(doc, "inter_company_order_reference", "") or "")
			and frappe.has_permission(PURCHASE_ORDER_DOCTYPE, "write", doc=doc)
		),
		"can_submit": not blockers,
		"workflow_readiness": workflow_readiness,
		"workflow_eligible": workflow_eligible,
		"persistence": "none",
		"status": "Review only",
		"source_of_truth": "ERPNext Purchase Order",
	}


@frappe.whitelist()
def get_purchase_order_submit_preview(purchase_order: str) -> dict[str, Any]:
	"""Review one Purchase Order before standard submit/workflow action; no writes occur."""
	return _build_preview(_get_purchase_order(purchase_order))


@frappe.whitelist()
def search_purchase_order_draft_items(
	purchase_order: str,
	txt: str = "",
	limit: int = 20,
) -> list[dict[str, Any]]:
	"""Search permitted purchase Items while editing one existing draft Purchase Order."""
	doc = _get_purchase_order(purchase_order)
	_validate_purchase_order_branch(doc)
	if cint(getattr(doc, "docstatus", 0)) != 0 or not frappe.has_permission(PURCHASE_ORDER_DOCTYPE, "write", doc=doc):
		frappe.throw(_("You do not have permission to edit this Purchase Order."), frappe.PermissionError)
	filters: dict[str, Any] = {"is_purchase_item": 1, "disabled": 0}
	supplier = str(getattr(doc, "supplier", "") or "").strip()
	if supplier:
		filters["supplier"] = supplier
	return list(
		search_link(
			"Item",
			str(txt or ""),
			query="erpnext.controllers.queries.item_query",
			filters=filters,
			page_length=max(1, min(cint(limit) or 20, 50)),
			reference_doctype="Purchase Order Item",
			link_fieldname="item_code",
		)
	)


@frappe.whitelist()
def get_purchase_order_draft_item_pricing(
	purchase_order: str,
	item_code: str,
	qty: float | int = 1,
) -> dict[str, Any]:
	"""Resolve buying price for a new row using the saved Purchase Order context."""
	doc = _get_purchase_order(purchase_order)
	branch = _validate_purchase_order_branch(doc)
	if cint(getattr(doc, "docstatus", 0)) != 0 or not frappe.has_permission(PURCHASE_ORDER_DOCTYPE, "write", doc=doc):
		frappe.throw(_("You do not have permission to edit this Purchase Order."), frappe.PermissionError)
	item_code = str(item_code or "").strip()
	if not item_code:
		frappe.throw(_("Item is required."))
	_assert_read("Item", item_code)
	return resolve_purchase_item_pricing(
		item_code=item_code,
		company=str(getattr(doc, "company", "") or ""),
		supplier=str(getattr(doc, "supplier", "") or ""),
		branch=branch,
		warehouse=str(getattr(doc, "set_warehouse", "") or ""),
		posting_date=str(getattr(doc, "transaction_date", "") or ""),
		qty=flt(qty or 1),
		selected_price_list=str(getattr(doc, "buying_price_list", "") or ""),
		user=frappe.session.user,
		requested_price_list=str(getattr(doc, "buying_price_list", "") or ""),
	)


@frappe.whitelist(methods=["POST"])
def update_standard_purchase_order_draft(
	purchase_order: str,
	values: dict | str | None = None,
	expected_purchase_order_modified: str | None = None,
) -> dict[str, Any]:
	"""Update bounded fields on an existing draft Purchase Order before completion.

	Company, Supplier, Branch, Stock Location, Buying Price List and item identity
	remain protected. ERPNext recalculates totals and validates the draft on save.
	"""
	purchase_order = str(purchase_order or "").strip()
	if not purchase_order:
		frappe.throw(_("Purchase Order is required."))
	if not frappe.db.exists(PURCHASE_ORDER_DOCTYPE, purchase_order):
		frappe.throw(_("Purchase Order {0} does not exist.").format(purchase_order))

	frappe.db.sql(
		"SELECT name FROM `tabPurchase Order` WHERE name = %s FOR UPDATE",
		(purchase_order,),
	)
	doc = _get_purchase_order(purchase_order)
	_validate_purchase_order_branch(doc)
	if cint(getattr(doc, "docstatus", 0)) != 0:
		frappe.throw(_("Only draft Purchase Orders can be edited here."))
	if str(getattr(doc, "status", "") or "") in BLOCKED_DRAFT_STATUSES:
		frappe.throw(_("Purchase Order status {0} is not editable in standard purchasing.").format(doc.status))
	if cint(getattr(doc, "is_subcontracted", 0)) or cint(getattr(doc, "is_old_subcontracting_flow", 0)):
		frappe.throw(_("Subcontracting Purchase Orders require Advanced ERPNext review."))
	if cint(getattr(doc, "is_internal_supplier", 0)) or str(getattr(doc, "inter_company_order_reference", "") or ""):
		frappe.throw(_("Inter-company Purchase Orders require Advanced ERPNext review."))
	if not frappe.has_permission(PURCHASE_ORDER_DOCTYPE, "write", doc=doc):
		frappe.throw(_("You do not have permission to edit this Purchase Order."), frappe.PermissionError)

	expected_modified = str(expected_purchase_order_modified or "").strip()
	current_modified = str(getattr(doc, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(_("Purchase Order {0} changed after it was opened. Refresh before saving.").format(doc.name))

	values = frappe.parse_json(values) if isinstance(values, str) else dict(values or {})
	transaction_date = getdate(values.get("transaction_date") or getattr(doc, "transaction_date", None))
	parent_schedule = values.get("schedule_date") or getattr(doc, "schedule_date", None) or transaction_date
	parent_schedule = getdate(parent_schedule)
	if parent_schedule < transaction_date:
		frappe.throw(_("Required By date cannot be before the Order Date."))

	doc.transaction_date = transaction_date
	if doc.meta.has_field("schedule_date"):
		doc.schedule_date = parent_schedule
	if doc.meta.has_field("terms"):
		doc.terms = str(values.get("terms") or "").strip()

	current_rows = {
		str(getattr(row, "name", "") or ""): row
		for row in list(getattr(doc, "items", None) or [])
		if str(getattr(row, "name", "") or "")
	}
	requested_rows = values.get("items") or []
	if not isinstance(requested_rows, list):
		frappe.throw(_("Purchase Order items are invalid."))
	if not requested_rows:
		frappe.throw(_("Add at least one Purchase Order item."))
	if len(requested_rows) > MAX_ITEMS:
		frappe.throw(_("A Purchase Order can contain at most {0} items here.").format(MAX_ITEMS))
	for index, requested in enumerate(requested_rows, start=1):
		if not isinstance(requested, dict):
			frappe.throw(_("Purchase Order item row {0} is invalid.").format(index))
		row_name = str(requested.get("name") or "").strip()
		row = current_rows.get(row_name) if row_name else None
		if row_name and not row:
			frappe.throw(_("Purchase Order item row {0} is no longer part of this draft. Refresh and try again.").format(index))

		item_code = str(requested.get("item_code") or "").strip()
		if row:
			if item_code and item_code != str(getattr(row, "item_code", "") or "").strip():
				frappe.throw(_("Existing Purchase Order item identity cannot be replaced here. Add a new item row instead."))
		else:
			if not item_code:
				frappe.throw(_("Item is required on new Purchase Order row {0}.").format(index))
			_assert_read("Item", item_code)
			row = doc.append("items", {"item_code": item_code})
			default_warehouse = str(getattr(doc, "set_warehouse", "") or "").strip()
			if default_warehouse and row.meta.has_field("warehouse"):
				row.warehouse = default_warehouse

		qty = flt(requested.get("qty"))
		row_schedule = getdate(requested.get("schedule_date") or parent_schedule)
		if qty <= 0:
			frappe.throw(_("Quantity on row {0} must be greater than zero.").format(index))
		if row_schedule < transaction_date:
			frappe.throw(_("Required By date on row {0} cannot be before the Order Date.").format(index))

		rate_value = requested.get("rate")
		if not row_name and rate_value in (None, ""):
			pricing = resolve_purchase_item_pricing(
				item_code=item_code,
				company=str(getattr(doc, "company", "") or ""),
				supplier=str(getattr(doc, "supplier", "") or ""),
				branch=_document_branch(doc),
				warehouse=str(getattr(row, "warehouse", "") or getattr(doc, "set_warehouse", "") or ""),
				posting_date=str(transaction_date),
				qty=qty,
				selected_price_list=str(getattr(doc, "buying_price_list", "") or ""),
				user=frappe.session.user,
				requested_price_list=str(getattr(doc, "buying_price_list", "") or ""),
			)
			rate_value = pricing.get("rate")
			if rate_value is None:
				frappe.throw(
					_("No buying price could be resolved for Item {0}. Enter the agreed buying rate before saving.").format(
						item_code
					)
				)
		rate = flt(rate_value)
		if rate < 0:
			frappe.throw(_("Buying Rate on row {0} cannot be negative.").format(index))

		row.qty = qty
		row.rate = rate
		row.schedule_date = row_schedule

	if hasattr(doc, "set_missing_values"):
		doc.set_missing_values()

	doc.save()
	doc.reload()
	return _build_preview(doc)


@frappe.whitelist(methods=["POST"])
def apply_standard_purchase_order_workflow_action(
	purchase_order: str,
	action: str,
	expected_purchase_order_modified: str | None = None,
	expected_workflow_state: str | None = None,
) -> dict[str, Any]:
	purchase_order = str(purchase_order or "").strip()
	action = str(action or "").strip()
	if not purchase_order or not action:
		frappe.throw(_("Purchase Order and workflow action are required."))
	if not frappe.db.exists(PURCHASE_ORDER_DOCTYPE, purchase_order):
		frappe.throw(_("Purchase Order {0} does not exist.").format(purchase_order))
	_assert_read(PURCHASE_ORDER_DOCTYPE, purchase_order)

	frappe.db.sql(
		"SELECT name FROM `tabPurchase Order` WHERE name = %s FOR UPDATE",
		(purchase_order,),
	)
	doc = _get_purchase_order(purchase_order)
	_validate_purchase_order_branch(doc)
	_item_preview(doc)

	expected_modified = str(expected_purchase_order_modified or "").strip()
	current_modified = str(getattr(doc, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(
			_("Purchase Order {0} changed after the review. Refresh before applying a workflow action.").format(
				doc.name
			)
		)

	preview = _build_preview(doc)
	if not preview.get("workflow_eligible"):
		frappe.throw(
			_("This Purchase Order is not eligible for a standard EdgeSuite workflow action.")
		)

	result = apply_document_workflow_action(
		doctype=PURCHASE_ORDER_DOCTYPE,
		name=doc.name,
		action=action,
		expected_modified=expected_modified,
		expected_state=str(expected_workflow_state or ""),
	)
	if cint(result.get("docstatus")) == 1:
		current = _get_purchase_order(doc.name)
		result.update(
			{
				"company": str(getattr(current, "company", "") or ""),
				"branch": _document_branch(current),
				"supplier": str(getattr(current, "supplier", "") or ""),
				"status": str(getattr(current, "status", "") or "Submitted"),
				"next_actions": _submitted_next_actions(current),
				"source_of_truth": "Frappe Workflow / ERPNext Purchase Order",
			}
		)
	return result


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
	doc.reload()

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
		"next_actions": _submitted_next_actions(doc),
		"source_of_truth": "ERPNext Purchase Order submit",
	}
