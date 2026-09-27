from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note as erpnext_make_delivery_note_from_invoice
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note as erpnext_make_delivery_note

from retailedge.branch_context import resolve_branch_from_warehouse
from retailedge.operating_context import get_operating_context
from retailedge.professional_quotation import _validate_shipping_rule
from retailedge.professional_selling import (
	_assert_read,
	_permission,
	_validate_stored_operational_branch,
)


def _source_branch(doc) -> str:
	return str(doc.get("branch") or doc.get("retailedge_branch") or "").strip()


def _validate_source_against_operating_context(source) -> tuple[str, str]:
	source_label = str(getattr(source, "doctype", "") or "Selling Document").strip()
	company = str(source.get("company") or "").strip()
	if not company:
		frappe.throw(_("The {0} has no Company.").format(source_label))
	_assert_read("Company", company)

	branch = _validate_stored_operational_branch(
		company=company,
		branch=_source_branch(source),
		label=_("Submitted {0}").format(source_label),
	)

	operating = get_operating_context() or {}
	operating_company = str(operating.get("company") or "").strip()
	operating_branch = str(operating.get("branch") or "").strip()
	if operating_company and operating_company != company:
		frappe.throw(
			_(
				"The {0} belongs to another Company. Change Operating Context before creating its Delivery Note."
			).format(source_label)
		)
	if operating_branch and branch and operating_branch != branch:
		frappe.throw(_("{0} Branch does not match the current Operating Branch.").format(source_label))
	return company, branch


def _lock_sales_order(name: str) -> None:
	rows = frappe.db.sql(
		"SELECT name FROM `tabSales Order` WHERE name = %s FOR UPDATE",
		(name,),
	)
	if not rows:
		frappe.throw(_("Sales Order {0} no longer exists.").format(name))


def _existing_draft_delivery_for_sales_order(sales_order: str):
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT dn.name
		FROM `tabDelivery Note` dn
		INNER JOIN `tabDelivery Note Item` item ON item.parent = dn.name
		WHERE dn.docstatus = 0 AND item.against_sales_order = %s
		ORDER BY dn.creation ASC
		LIMIT 3
		""",
		(sales_order,),
		as_dict=True,
	)
	if len(rows) > 1:
		frappe.throw(
			_("Multiple draft Delivery Notes already reference Sales Order {0}. Review them before creating another delivery.").format(sales_order)
		)
	if not rows:
		return None
	doc = frappe.get_doc("Delivery Note", rows[0].name)
	if not frappe.has_permission("Delivery Note", "read", doc=doc):
		frappe.throw(
			_("A draft Delivery Note already exists for this Sales Order, but you do not have permission to open it."),
			frappe.PermissionError,
		)
	linked_orders = {
		str(row.get("against_sales_order") or "").strip()
		for row in list(doc.get("items") or [])
		if str(row.get("against_sales_order") or "").strip()
	}
	if linked_orders != {sales_order}:
		frappe.throw(
			_("The existing draft Delivery Note combines multiple Sales Orders. Use Advanced ERPNext review.")
		)
	return doc


def _lock_sales_invoice(name: str) -> None:
	rows = frappe.db.sql(
		"SELECT name FROM `tabSales Invoice` WHERE name = %s FOR UPDATE",
		(name,),
	)
	if not rows:
		frappe.throw(_("Sales Invoice {0} no longer exists.").format(name))


def _existing_delivery_for_invoice(sales_invoice: str):
	"""Return the first Delivery Note ever created directly from this Sales Invoice.

	Professional Selling treats direct Sales Invoice -> Delivery Note conversion as
	one idempotent workflow. A second click must reopen the existing Delivery Note,
	not create another one. If that Delivery Note was cancelled, normal ERPNext
	Amend is the safe continuation path so document lineage remains intact.
	"""
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT dn.name, dn.docstatus
		FROM `tabDelivery Note` dn
		INNER JOIN `tabDelivery Note Item` item ON item.parent = dn.name
		WHERE item.against_sales_invoice = %s
		ORDER BY dn.creation ASC
		LIMIT 1
		""",
		(sales_invoice,),
		as_dict=True,
	)
	if not rows:
		return None

	name = str(rows[0].name or "").strip()
	if not name:
		return None

	doc = frappe.get_doc("Delivery Note", name)
	if not frappe.has_permission("Delivery Note", "read", doc=doc):
		frappe.throw(
			_(
				"A Delivery Note already exists for this Sales Invoice, but you do not have permission to open it."
			),
			frappe.PermissionError,
		)
	if int(doc.docstatus or 0) == 2:
		frappe.throw(
			_(
				"Sales Invoice {0} already created Delivery Note {1}. That Delivery Note is cancelled; "
				"open it and use Amend instead of creating another Delivery Note."
			).format(sales_invoice, doc.name)
		)
	return doc


def _delivery_response(
	target,
	*,
	branch: str,
	source_sales_invoice: str = "",
	source_sales_order: str = "",
	existing: bool = False,
) -> dict[str, Any]:
	return {
		"doctype": target.doctype,
		"name": target.name,
		"docstatus": target.docstatus,
		"customer": target.customer,
		"company": target.company,
		"branch": target.get("branch") or target.get("retailedge_branch") or branch,
		"shipping_rule": target.get("shipping_rule") or "",
		"grand_total": target.grand_total,
		"currency": target.currency,
		"source_sales_invoice": source_sales_invoice,
		"source_sales_order": source_sales_order,
		"existing": existing,
		"route": f"/app/delivery-note/{target.name}",
	}


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
			warehouse_branch = _validate_stored_operational_branch(
				company=company,
				branch=warehouse_branch,
				label=_("Delivery Stock Location"),
			)
			resolved_branches.add(warehouse_branch)

	if len(resolved_branches) > 1:
		frappe.throw(
			_(
				"The mapped Delivery Note spans Stock Locations from multiple Branches. "
				"Use the native Delivery Note workflow to split the delivery safely."
			)
		)
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
	_lock_sales_order(source.name)
	existing = _existing_draft_delivery_for_sales_order(source.name)
	if existing:
		existing_branch = _source_branch(existing) or source_branch
		return _delivery_response(
			existing,
			branch=existing_branch,
			source_sales_order=source.name,
			existing=True,
		)

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
	return _delivery_response(target, branch=mapped_branch, source_sales_order=source.name)


@frappe.whitelist(methods=["POST"])
def create_delivery_note_from_sales_invoice(sales_invoice: str) -> dict[str, Any]:
	"""Create or reopen the single Delivery Note directly linked to a Sales Invoice.

	ERPNext's native Sales Invoice mapper owns invoice-item linkage and remaining
	delivery quantities. Professional Selling adds a source-level lock and an
	idempotency check so repeated clicks cannot create duplicate direct Delivery
	Notes from the same Sales Invoice.
	"""
	if not _permission("Delivery Note", "create"):
		frappe.throw(_("You do not have permission to create Delivery Note."), frappe.PermissionError)

	sales_invoice = str(sales_invoice or "").strip()
	_assert_read("Sales Invoice", sales_invoice)
	source = frappe.get_doc("Sales Invoice", sales_invoice)
	if source.docstatus != 1:
		frappe.throw(_("Submit the Sales Invoice before creating a Delivery Note from it."))
	if source.get("is_return"):
		frappe.throw(_("Return / Credit Note invoices cannot create a Delivery Note."))
	if source.get("update_stock"):
		frappe.throw(
			_(
				"This Sales Invoice already posted stock. Creating another Delivery Note would duplicate stock movement."
			)
		)

	company, source_branch = _validate_source_against_operating_context(source)
	_lock_sales_invoice(source.name)
	existing = _existing_delivery_for_invoice(source.name)
	if existing:
		existing_branch = _source_branch(existing) or source_branch
		return _delivery_response(
			existing,
			branch=existing_branch,
			source_sales_invoice=source.name,
			existing=True,
		)

	target = erpnext_make_delivery_note_from_invoice(source.name)
	if not target or target.doctype != "Delivery Note":
		frappe.throw(_("ERPNext could not prepare a Delivery Note from this Sales Invoice."))
	if target.docstatus != 0:
		frappe.throw(_("ERPNext returned a non-draft Delivery Note mapping; creation was stopped."))
	if not target.get("items"):
		frappe.throw(_("There are no remaining deliverable quantities on this Sales Invoice."))
	if str(target.get("company") or "") != company:
		frappe.throw(_("The mapped Delivery Note Company does not match the Sales Invoice."))

	mapped_branch = _validate_mapped_delivery_stock_context(
		target,
		company=company,
		source_branch=source_branch,
	)
	if target.get("shipping_rule"):
		_validate_shipping_rule(target.shipping_rule, company=company)

	target.insert()
	return _delivery_response(target, branch=mapped_branch, source_sales_invoice=source.name)
