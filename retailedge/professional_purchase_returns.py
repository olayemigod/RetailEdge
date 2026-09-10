from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.professional_purchasing import (
	_assert_create,
	_assert_read,
	_permission,
	_validate_native_purchase_return_source,
	_validate_native_purchase_return_target,
)

PURCHASE_RECEIPT_DOCTYPE = "Purchase Receipt"
PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"
SOURCE_TYPES = {
	"purchase_receipt": PURCHASE_RECEIPT_DOCTYPE,
	"purchase_invoice": PURCHASE_INVOICE_DOCTYPE,
}


def _source_doctype(source_type: str | None) -> str:
	key = str(source_type or "").strip().lower()
	if key not in SOURCE_TYPES:
		frappe.throw(_("Choose Purchase Receipt return or Supplier Debit Note."))
	return SOURCE_TYPES[key]


def _source_label(doctype: str) -> str:
	return PURCHASE_RECEIPT_DOCTYPE if doctype == PURCHASE_RECEIPT_DOCTYPE else PURCHASE_INVOICE_DOCTYPE


def _get_source(source_type: str | None, source_name: str | None, *, lock: bool = False) -> Any:
	doctype = _source_doctype(source_type)
	name = str(source_name or "").strip()
	if not name:
		frappe.throw(_("{0} is required.").format(_source_label(doctype)))
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(_source_label(doctype), name))
	_assert_read(doctype, name)
	_assert_create(doctype)
	if lock:
		# Serialise return posting for one submitted source so concurrent requests
		# cannot both map the same remaining returnable quantity.
		frappe.db.sql(f"SELECT name FROM `tab{doctype}` WHERE name = %s FOR UPDATE", (name,))
	source = frappe.get_doc(doctype, name)
	_validate_native_purchase_return_source(source, source_label=_source_label(doctype))
	return source


def _map_target(source: Any) -> tuple[Any, list[Any], str]:
	doctype = str(source.doctype or "")
	company, source_branch = _validate_native_purchase_return_source(source, source_label=_source_label(doctype))
	if doctype == PURCHASE_RECEIPT_DOCTYPE:
		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_return

		target = make_purchase_return(source.name)
	else:
		from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import make_debit_note

		target = make_debit_note(source.name)
	items, target_branch = _validate_native_purchase_return_target(
		source,
		target,
		target_doctype=doctype,
		source_label=_source_label(doctype),
		company=company,
		source_branch=source_branch,
	)
	return target, items, target_branch


def _stock_effect_enabled(target: Any) -> bool:
	if str(target.doctype or "") == PURCHASE_RECEIPT_DOCTYPE:
		return True
	return bool(cint(getattr(target, "update_stock", 0)))


def _item_stock_controls(item_code: str) -> dict[str, bool]:
	if not item_code:
		return {"has_serial_no": False, "has_batch_no": False}
	values = frappe.db.get_value(
		"Item",
		item_code,
		["has_serial_no", "has_batch_no"],
		as_dict=True,
	) or {}
	return {
		"has_serial_no": bool(cint(values.get("has_serial_no"))),
		"has_batch_no": bool(cint(values.get("has_batch_no"))),
	}


def _preview_items(target: Any, items: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
	rows: list[dict[str, Any]] = []
	blockers: list[dict[str, str]] = []
	stock_effect = _stock_effect_enabled(target)
	company = str(getattr(target, "company", "") or "")
	for item in items:
		item_code = str(getattr(item, "item_code", "") or "").strip()
		qty = flt(getattr(item, "qty", 0))
		if qty >= 0:
			frappe.throw(_("ERPNext mapped a non-return quantity for Item {0}.").format(item_code or _("Unknown")))
		warehouse = str(getattr(item, "warehouse", "") or "").strip()
		if stock_effect and warehouse:
			warehouse_company = str(frappe.db.get_value("Warehouse", warehouse, "company") or "")
			if warehouse_company != company:
				frappe.throw(_("Stock Location {0} does not belong to Company {1}.").format(warehouse, company))
		controls = _item_stock_controls(item_code) if stock_effect else {"has_serial_no": False, "has_batch_no": False}
		if controls["has_serial_no"]:
			blockers.append({
				"key": "serial_number",
				"item_code": item_code,
				"label": _("Serial Number handling requires Advanced ERPNext"),
			})
		if controls["has_batch_no"]:
			blockers.append({
				"key": "batch",
				"item_code": item_code,
				"label": _("Batch handling requires Advanced ERPNext"),
			})
		rows.append(
			{
				"name": str(getattr(item, "name", "") or ""),
				"item_code": item_code,
				"item_name": str(getattr(item, "item_name", "") or item_code),
				"qty": qty,
				"uom": str(getattr(item, "uom", "") or getattr(item, "stock_uom", "") or ""),
				"warehouse": warehouse,
				"rate": flt(getattr(item, "rate", 0)),
				"amount": flt(getattr(item, "amount", 0)),
				"requires_serial_no": controls["has_serial_no"],
				"requires_batch": controls["has_batch_no"],
			}
		)
	return rows, blockers


def _build_review(source: Any) -> tuple[Any, dict[str, Any]]:
	target, mapped_items, target_branch = _map_target(source)
	items, blockers = _preview_items(target, mapped_items)
	can_submit = bool(not blockers and _permission(source.doctype, "submit"))
	return target, {
		"source_type": "purchase_receipt" if source.doctype == PURCHASE_RECEIPT_DOCTYPE else "purchase_invoice",
		"source_doctype": source.doctype,
		"source_name": source.name,
		"source_modified": str(getattr(source, "modified", "") or ""),
		"target_doctype": target.doctype,
		"return_against": str(getattr(target, "return_against", "") or ""),
		"company": str(getattr(target, "company", "") or ""),
		"branch": target_branch,
		"supplier": str(getattr(target, "supplier", "") or ""),
		"supplier_name": str(getattr(target, "supplier_name", "") or getattr(source, "supplier_name", "") or getattr(target, "supplier", "") or ""),
		"posting_date": str(getattr(target, "posting_date", "") or ""),
		"update_stock": bool(cint(getattr(target, "update_stock", 0))),
		"stock_effect": _stock_effect_enabled(target),
		"items": items,
		"blockers": blockers,
		"standard_return_eligible": not blockers,
		"can_submit": can_submit,
		"persistence": "none",
		"posting_status": "Preview only",
		"source_of_truth": "ERPNext canonical purchase return mapper",
	}


@frappe.whitelist()
def get_purchase_return_review(source_type: str, source_name: str) -> dict[str, Any]:
	"""Preview a canonical ERPNext Purchase Return / Debit Note without persistence."""
	source = _get_source(source_type, source_name)
	_target, review = _build_review(source)
	return review


@frappe.whitelist(methods=["POST"])
def submit_purchase_return_review(
	source_type: str,
	source_name: str,
	expected_source_modified: str | None = None,
) -> dict[str, Any]:
	"""Insert and submit one standard canonical Purchase Return / Debit Note."""
	source = _get_source(source_type, source_name, lock=True)
	if not _permission(source.doctype, "submit"):
		frappe.throw(_("You do not have permission to submit {0}.").format(_source_label(source.doctype)), frappe.PermissionError)

	expected_modified = str(expected_source_modified or "").strip()
	current_modified = str(getattr(source, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(
			_("{0} {1} changed after the return preview. Refresh the preview before submitting.").format(
				_source_label(source.doctype), source.name
			)
		)

	target, review = _build_review(source)
	if review["blockers"]:
		labels = ", ".join(str(row.get("label") or row.get("key") or "") for row in review["blockers"])
		frappe.throw(_("This return requires Advanced ERPNext handling: {0}").format(labels))
	if not review["can_submit"]:
		frappe.throw(_("You do not have permission to submit {0}.").format(_source_label(source.doctype)), frappe.PermissionError)

	# ERPNext remains authoritative. The mapped return is inserted and submitted
	# as the current user; no direct Stock Ledger / General Ledger writes occur here.
	target.insert()
	target.submit()
	if cint(getattr(target, "docstatus", 0)) != 1:
		frappe.throw(_("ERPNext did not submit {0} {1}.").format(target.doctype, target.name))

	return {
		"doctype": target.doctype,
		"name": target.name,
		"docstatus": cint(target.docstatus),
		"return_against": str(getattr(target, "return_against", "") or ""),
		"company": str(getattr(target, "company", "") or ""),
		"supplier": str(getattr(target, "supplier", "") or ""),
		"branch": review["branch"],
		"item_count": len(review["items"]),
		"update_stock": review["update_stock"],
		"posting_status": "Submitted",
		"source_of_truth": "ERPNext document submit",
	}
