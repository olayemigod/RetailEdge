from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

ITEM_DOCTYPE = "Item"
MAX_LINK_RESULTS = 20


@frappe.whitelist()
def get_simple_item_context() -> dict[str, Any]:
	_assert_can_create_item()
	return {
		"title": _("Simple Product"),
		"subtitle": _("Create an ERPNext Item without exposing cost or valuation fields."),
		"submit_label": _("Create Product"),
		"full_form_doctype": ITEM_DOCTYPE,
		"defaults": {
			"item_code": "",
			"item_name": "",
			"is_stock_item": 1,
			"item_group": _default_item_group(),
			"stock_uom": _default_stock_uom(),
			"description": "",
			"barcode": "",
		},
		"limits": {"link_results": MAX_LINK_RESULTS},
		"capabilities": {
			"native_form_fallback": True,
			"cost_fields_exposed": False,
			"pricing_fields_exposed": False,
		},
	}


@frappe.whitelist()
def search_simple_item_options(
	fieldname: str,
	txt: str = "",
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_can_create_item()
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	if fieldname == "item_group":
		return search_link(
			"Item Group",
			txt or "",
			filters={"is_group": 0},
			page_length=limit,
			reference_doctype=ITEM_DOCTYPE,
			link_fieldname="item_group",
		)
	if fieldname == "stock_uom":
		return search_link(
			"UOM",
			txt or "",
			filters={"enabled": 1},
			page_length=limit,
			reference_doctype=ITEM_DOCTYPE,
			link_fieldname="stock_uom",
		)
	frappe.throw(_("Unsupported Simple Product search field: {0}").format(fieldname))
	return []


@frappe.whitelist(methods=["POST"])
def create_simple_item(values: dict | str | None = None) -> dict[str, Any]:
	_assert_can_create_item()
	values = _coerce_values(values)
	item_code = str(values.get("item_code") or "").strip()
	if not item_code:
		frappe.throw(_("Item Code is required."))
	item_name = str(values.get("item_name") or item_code).strip()
	item_group = str(values.get("item_group") or _default_item_group() or "").strip()
	stock_uom = str(values.get("stock_uom") or _default_stock_uom() or "").strip()
	if not item_group:
		frappe.throw(_("Item Group is required. Configure an ERPNext default or select one."))
	if not stock_uom:
		frappe.throw(_("Stock UOM is required. Configure an ERPNext default or select one."))
	_assert_read_permission("Item Group", item_group)
	_assert_read_permission("UOM", stock_uom)
	_validate_leaf_item_group(item_group)
	_validate_uom(stock_uom)

	doc = frappe.new_doc(ITEM_DOCTYPE)
	doc.item_code = item_code
	doc.item_name = item_name
	doc.is_stock_item = cint(values.get("is_stock_item", 1))
	doc.item_group = item_group
	doc.stock_uom = stock_uom
	meta = frappe.get_meta(ITEM_DOCTYPE)
	description = str(values.get("description") or "").strip()
	if description and meta.has_field("description"):
		doc.description = description
	doc.insert()

	barcode = str(values.get("barcode") or "").strip()
	if barcode:
		_add_barcode_if_supported(doc, barcode)

	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"item_code": doc.item_code,
		"item_name": doc.item_name,
		"is_stock_item": cint(doc.is_stock_item),
		"item_group": doc.item_group,
		"stock_uom": doc.stock_uom,
		"route": f"/app/item/{doc.name}",
	}


def _add_barcode_if_supported(doc, barcode: str) -> None:
	meta = frappe.get_meta(ITEM_DOCTYPE)
	if not meta.has_field("barcodes"):
		return
	# Barcode is supporting master data, not valuation/pricing data. Append only after
	# the Item has a valid native document model; normal ERPNext validation remains authoritative.
	doc.append("barcodes", {"barcode": barcode})
	doc.save()


def _default_item_group() -> str:
	return frappe.defaults.get_user_default("Item Group") or ""


def _default_stock_uom() -> str:
	return (
		frappe.defaults.get_user_default("UOM")
		or frappe.db.get_single_value("Stock Settings", "stock_uom")
		or "Nos"
	)


def _validate_leaf_item_group(name: str) -> None:
	if not frappe.db.exists("Item Group", name):
		frappe.throw(_("Item Group {0} does not exist.").format(name))
	if frappe.db.get_value("Item Group", name, "is_group"):
		frappe.throw(_("Item Group {0} must be a selectable leaf record.").format(name))


def _validate_uom(name: str) -> None:
	if not frappe.db.exists("UOM", name):
		frappe.throw(_("UOM {0} does not exist.").format(name))
	if frappe.db.get_value("UOM", name, "enabled") == 0:
		frappe.throw(_("UOM {0} is disabled.").format(name))


def _assert_can_create_item() -> None:
	if not frappe.has_permission(ITEM_DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Products."), frappe.PermissionError)


def _assert_read_permission(doctype: str, name: str) -> None:
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to use {0} {1}.").format(doctype, name), frappe.PermissionError)


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if isinstance(values, str):
		values = frappe.parse_json(values)
	return dict(values or {})
