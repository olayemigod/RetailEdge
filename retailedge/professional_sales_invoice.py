from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, nowdate

from erpnext.selling.doctype.sales_order.sales_order import (
	make_sales_invoice as erpnext_make_sales_invoice_from_order,
)
from erpnext.stock.doctype.delivery_note.delivery_note import (
	make_sales_invoice as erpnext_make_sales_invoice_from_delivery,
)

from retailedge.branch_context import resolve_branch_from_warehouse, validate_user_branch_access
from retailedge.guided_sales_invoice import create_simple_sales_invoice_draft
from retailedge.operating_context import get_operating_context
from retailedge.professional_quotation import _validate_shipping_rule
from retailedge.professional_selling import (
	MAX_LINK_RESULTS,
	_assert_read,
	_coerce_values,
	_permission,
	_validate_context,
)

INVOICE_DEFINITION: dict[str, Any] = {
	"key": "sales-invoice",
	"doctype": "Sales Invoice",
	"item_doctype": "Sales Invoice Item",
	"label": "Sales Invoice",
	"stage": "Invoice",
	"date_field": "posting_date",
	"party_field": "customer",
	"supports_shipping_rule": True,
	"supports_source_warehouse": True,
	"native_route": "/app/sales-invoice",
}

_SOURCE_CONFIG = {
	"quotation": {"doctype": "Quotation", "label": "Quotation"},
	"sales-order": {"doctype": "Sales Order", "label": "Sales Order"},
	"delivery-note": {"doctype": "Delivery Note", "label": "Delivery Note"},
}

_CHILD_IDENTITY_FIELDS = {
	"name",
	"parent",
	"parentfield",
	"parenttype",
	"doctype",
	"idx",
	"creation",
	"modified",
	"modified_by",
	"owner",
	"docstatus",
}

_QUOTATION_ITEM_FIELDS = (
	"item_code",
	"item_name",
	"description",
	"qty",
	"uom",
	"conversion_factor",
	"stock_uom",
	"rate",
	"price_list_rate",
	"discount_percentage",
	"discount_amount",
	"warehouse",
	"project",
	"cost_center",
)


def _field_exists(doctype: str, fieldname: str) -> bool:
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def _source_branch(doc) -> str:
	return str(doc.get("branch") or doc.get("retailedge_branch") or "").strip()


def _set_branch_if_supported(doc, branch: str) -> None:
	branch = str(branch or "").strip()
	if not branch:
		return
	for fieldname in ("branch", "retailedge_branch"):
		if doc.meta.has_field(fieldname):
			doc.set(fieldname, branch)
			return


def _validate_source_context(source, *, source_label: str) -> tuple[str, str]:
	company = str(source.get("company") or "").strip()
	if not company:
		frappe.throw(_("The {0} has no Company.").format(source_label))
	_assert_read("Company", company)

	branch = _source_branch(source)
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)

	operating = get_operating_context() or {}
	operating_company = str(operating.get("company") or "").strip()
	operating_branch = str(operating.get("branch") or "").strip()
	if operating_company and operating_company != company:
		frappe.throw(
			_("The {0} belongs to another Company. Change Operating Context before invoicing it.").format(
				source_label
			)
		)
	if operating_branch and branch and operating_branch != branch:
		frappe.throw(_("The {0} Branch does not match the current Operating Branch.").format(source_label))
	return company, branch


def _validate_invoice_stock_context(target, *, company: str, source_branch: str) -> str:
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
			validate_user_branch_access(
				warehouse_branch,
				user=frappe.session.user,
				company=company,
				throw=True,
			)
			resolved_branches.add(warehouse_branch)

	if len(resolved_branches) > 1:
		frappe.throw(
			_(
				"The mapped Sales Invoice spans Stock Locations from multiple Branches. "
				"Use the native ERPNext Sales Invoice workflow for this advanced case."
			)
		)
	mapped_branch = next(iter(resolved_branches), "") or _source_branch(target) or source_branch
	if operating_branch and mapped_branch and operating_branch != mapped_branch:
		frappe.throw(_("The mapped Sales Invoice Stock Location does not match the current Operating Branch."))
	return mapped_branch


def _invoice_response(
	doc,
	*,
	branch: str = "",
	source_doctype: str = "",
	source_name: str = "",
) -> dict[str, Any]:
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"customer": doc.customer,
		"company": doc.company,
		"branch": doc.get("branch") or doc.get("retailedge_branch") or branch,
		"selling_price_list": doc.get("selling_price_list") or "",
		"shipping_rule": doc.get("shipping_rule") or "",
		"grand_total": doc.grand_total,
		"currency": doc.currency,
		"source_doctype": source_doctype,
		"source_name": source_name,
		"route": f"/app/sales-invoice/{doc.name}",
	}


def _copy_child_row(source_row, target_child_doctype: str) -> dict[str, Any]:
	meta = frappe.get_meta(target_child_doctype)
	values: dict[str, Any] = {}
	source_values = source_row.as_dict() if hasattr(source_row, "as_dict") else dict(source_row)
	for fieldname, value in source_values.items():
		if fieldname in _CHILD_IDENTITY_FIELDS or not meta.has_field(fieldname):
			continue
		values[fieldname] = deepcopy(value)
	return values


def _copy_quotation_commercial_terms(source, target) -> None:
	header_fields = (
		"currency",
		"conversion_rate",
		"selling_price_list",
		"price_list_currency",
		"plc_conversion_rate",
		"customer_address",
		"contact_person",
		"shipping_address_name",
		"tax_category",
		"taxes_and_charges",
		"payment_terms_template",
		"terms",
		"additional_discount_percentage",
		"discount_amount",
		"apply_discount_on",
		"shipping_rule",
	)
	for fieldname in header_fields:
		if target.meta.has_field(fieldname) and source.meta.has_field(fieldname):
			target.set(fieldname, deepcopy(source.get(fieldname)))

	if target.meta.has_field("taxes") and source.get("taxes") is not None:
		target.set("taxes", [])
		for row in source.get("taxes") or []:
			target.append("taxes", _copy_child_row(row, "Sales Taxes and Charges"))


def _quotation_invoice_item(row) -> dict[str, Any]:
	values: dict[str, Any] = {}
	invoice_item_meta = frappe.get_meta("Sales Invoice Item")
	for fieldname in _QUOTATION_ITEM_FIELDS:
		if invoice_item_meta.has_field(fieldname) and row.get(fieldname) is not None:
			values[fieldname] = deepcopy(row.get(fieldname))
	return values


@frappe.whitelist()
def get_professional_sales_invoice_capability() -> dict[str, Any]:
	available = bool(frappe.db.exists("DocType", "Sales Invoice"))
	return {
		**INVOICE_DEFINITION,
		"available": available,
		"can_read": _permission("Sales Invoice", "read"),
		"can_create": _permission("Sales Invoice", "create"),
		"shipping_rule_field": available and _field_exists("Sales Invoice", "shipping_rule"),
		"selling_price_list_field": available and _field_exists("Sales Invoice", "selling_price_list"),
		"source_warehouse_field": available and _field_exists("Sales Invoice", "set_warehouse"),
		"conversion_sources": ["quotation", "sales-order", "delivery-note"],
	}


@frappe.whitelist()
def get_recent_professional_sales_invoices(limit: int = 8) -> list[dict[str, Any]]:
	if not _permission("Sales Invoice", "read"):
		frappe.throw(_("You do not have permission to view Sales Invoice."), frappe.PermissionError)
	limit = max(1, min(cint(limit) or 8, 20))
	fields = [
		"name",
		"docstatus",
		"modified",
		"customer",
		"posting_date",
		"status",
		"grand_total",
		"currency",
	]
	if _field_exists("Sales Invoice", "shipping_rule"):
		fields.append("shipping_rule")
	return [
		dict(row)
		for row in frappe.get_list(
			"Sales Invoice",
			fields=fields,
			order_by="modified desc",
			limit_page_length=limit,
		)
	]


@frappe.whitelist()
def search_professional_invoice_shipping_rules(
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	if not _permission("Sales Invoice", "create"):
		frappe.throw(_("You do not have permission to create Sales Invoice."), frappe.PermissionError)
	values = _coerce_values(values)
	company, _branch, _warehouse = _validate_context(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	return search_link(
		"Shipping Rule",
		txt or "",
		filters={"disabled": 0, "shipping_rule_type": "Selling", "company": company},
		page_length=limit,
		reference_doctype="Sales Invoice",
		link_fieldname="shipping_rule",
	)


@frappe.whitelist()
def search_professional_invoice_sources(
	source: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	source = str(source or "").strip()
	config = _SOURCE_CONFIG.get(source)
	if not config:
		frappe.throw(_("Unsupported Sales Invoice source: {0}").format(source))
	if not _permission("Sales Invoice", "create") or not _permission(config["doctype"], "read"):
		frappe.throw(
			_("You do not have permission to create Sales Invoice from {0}.").format(config["label"]),
			frappe.PermissionError,
		)

	values = _coerce_values(values)
	company, _branch, _warehouse = _validate_context(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	filters: dict[str, Any] = {"docstatus": 1, "company": company}
	link_fieldname = None

	if source == "quotation":
		filters.update(
			{
				"quotation_to": "Customer",
				"status": [
					"not in",
					["Partially Ordered", "Ordered", "Lost", "Cancelled", "Expired"],
				],
			}
		)
		link_fieldname = "quotation"
	elif source == "sales-order":
		filters.update(
			{
				"status": ["not in", ["Closed", "Completed", "Cancelled"]],
				"billing_status": ["!=", "Fully Billed"],
			}
		)
		link_fieldname = "sales_order"
	else:
		filters.update(
			{
				"status": ["not in", ["Closed", "Completed", "Cancelled", "Return"]],
				"per_billed": ["<", 100],
			}
		)
		link_fieldname = "delivery_note"

	return search_link(
		config["doctype"],
		txt or "",
		filters=filters,
		page_length=limit,
		reference_doctype="Sales Invoice",
		link_fieldname=link_fieldname,
	)


@frappe.whitelist(methods=["POST"])
def create_professional_sales_invoice_draft(
	values: dict | str | None = None,
) -> dict[str, Any]:
	"""Reuse the guarded invoice engine, then apply ERPNext Shipping Rule to its draft."""
	values = _coerce_values(values)
	shipping_rule = str(values.pop("shipping_rule", "") or "").strip()
	company, _branch, _warehouse = _validate_context(values)
	if shipping_rule:
		_validate_shipping_rule(shipping_rule, company=company)

	result = create_simple_sales_invoice_draft(values)
	doc = frappe.get_doc("Sales Invoice", result["name"])
	if doc.docstatus != 0:
		frappe.throw(
			_("Sales Invoice creation stopped because the guarded invoice engine returned a non-draft document.")
		)
	if shipping_rule:
		doc.shipping_rule = shipping_rule
		doc.apply_shipping_rule()
		doc.save()
	return _invoice_response(doc, branch=result.get("branch") or "")


@frappe.whitelist(methods=["POST"])
def create_sales_invoice_from_quotation(quotation: str) -> dict[str, Any]:
	"""Create a draft invoice directly from the submitted quotation's accepted terms.

	ERPNext v16 has no native Quotation -> Sales Invoice mapper. This path does
	not create a hidden Sales Order and does not reprice the accepted Quotation.
	ERPNext still validates the newly inserted Sales Invoice draft.
	"""
	if not _permission("Sales Invoice", "create"):
		frappe.throw(_("You do not have permission to create Sales Invoice."), frappe.PermissionError)
	quotation = str(quotation or "").strip()
	_assert_read("Quotation", quotation)
	source = frappe.get_doc("Quotation", quotation)
	if source.docstatus != 1:
		frappe.throw(_("Submit the Quotation before creating a Sales Invoice from it."))
	if str(source.get("quotation_to") or "") != "Customer":
		frappe.throw(_("Only Customer Quotations can be converted directly to Sales Invoice."))
	status = str(source.get("status") or "")
	if status in {"Partially Ordered", "Ordered"}:
		frappe.throw(
			_("This Quotation already has a Sales Order. Create the Sales Invoice from that Sales Order instead.")
		)
	if status in {"Lost", "Cancelled", "Expired"}:
		frappe.throw(_("This Quotation is not open for invoicing."))

	company, branch = _validate_source_context(source, source_label="Quotation")
	if source.get("shipping_rule"):
		_validate_shipping_rule(source.shipping_rule, company=company)

	target = frappe.new_doc("Sales Invoice")
	target.company = company
	target.customer = source.party_name
	target.posting_date = nowdate()
	target.update_stock = 0
	_set_branch_if_supported(target, branch)
	_copy_quotation_commercial_terms(source, target)

	for row in source.get("items") or []:
		if not row.get("item_code"):
			continue
		_assert_read("Item", row.item_code)
		target.append("items", _quotation_invoice_item(row))
	if not target.get("items"):
		frappe.throw(_("The Quotation has no invoiceable items."))

	mapped_branch = _validate_invoice_stock_context(target, company=company, source_branch=branch)
	# Draft insertion only. ERPNext validates accounts, taxes, pricing references,
	# Selling Settings and document linkage rules on insert.
	target.insert()
	return _invoice_response(
		target,
		branch=mapped_branch,
		source_doctype="Quotation",
		source_name=source.name,
	)


def _create_invoice_from_native_mapper(source_doctype: str, source_name: str, mapper) -> dict[str, Any]:
	if not _permission("Sales Invoice", "create"):
		frappe.throw(_("You do not have permission to create Sales Invoice."), frappe.PermissionError)
	source_name = str(source_name or "").strip()
	_assert_read(source_doctype, source_name)
	source = frappe.get_doc(source_doctype, source_name)
	if source.docstatus != 1:
		frappe.throw(_("Submit the {0} before creating a Sales Invoice from it.").format(source_doctype))

	company, source_branch = _validate_source_context(source, source_label=source_doctype)
	target = mapper(source.name)
	if not target or target.doctype != "Sales Invoice":
		frappe.throw(_("ERPNext could not prepare a Sales Invoice from this {0}.").format(source_doctype))
	if target.docstatus != 0:
		frappe.throw(_("ERPNext returned a non-draft Sales Invoice mapping; creation was stopped."))
	if not target.get("items"):
		frappe.throw(_("There are no remaining billable quantities on this {0}.").format(source_doctype))
	if str(target.get("company") or "") != company:
		frappe.throw(_("The mapped Sales Invoice Company does not match the source {0}.").format(source_doctype))

	mapped_branch = _validate_invoice_stock_context(
		target,
		company=company,
		source_branch=source_branch,
	)
	_set_branch_if_supported(target, mapped_branch)
	if target.get("shipping_rule"):
		_validate_shipping_rule(target.shipping_rule, company=company)
	target.insert()
	return _invoice_response(
		target,
		branch=mapped_branch,
		source_doctype=source_doctype,
		source_name=source.name,
	)


@frappe.whitelist(methods=["POST"])
def create_sales_invoice_from_sales_order(sales_order: str) -> dict[str, Any]:
	return _create_invoice_from_native_mapper(
		"Sales Order",
		sales_order,
		erpnext_make_sales_invoice_from_order,
	)


@frappe.whitelist(methods=["POST"])
def create_sales_invoice_from_delivery_note(delivery_note: str) -> dict[str, Any]:
	return _create_invoice_from_native_mapper(
		"Delivery Note",
		delivery_note,
		erpnext_make_sales_invoice_from_delivery,
	)
