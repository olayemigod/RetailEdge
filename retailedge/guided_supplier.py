from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

SUPPLIER_DOCTYPE = "Supplier"
MAX_LINK_RESULTS = 20


@frappe.whitelist()
def get_simple_supplier_context() -> dict[str, Any]:
	_assert_can_create_supplier()
	return {
		"title": _("Simple Supplier"),
		"subtitle": _("Create an ERPNext Supplier using the common business fields only."),
		"submit_label": _("Create Supplier"),
		"full_form_doctype": SUPPLIER_DOCTYPE,
		"defaults": {
			"supplier_name": "",
			"supplier_type": "Company",
			"supplier_group": _default_supplier_group(),
			"mobile_no": "",
			"email_id": "",
			"tax_id": "",
		},
		"options": {"supplier_types": ["Company", "Individual"]},
		"limits": {"link_results": MAX_LINK_RESULTS},
		"capabilities": {"native_form_fallback": True},
	}


@frappe.whitelist()
def search_simple_supplier_options(
	fieldname: str,
	txt: str = "",
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_can_create_supplier()
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	if fieldname == "supplier_group":
		return search_link(
			"Supplier Group",
			txt or "",
			filters={"is_group": 0},
			page_length=limit,
			reference_doctype=SUPPLIER_DOCTYPE,
			link_fieldname="supplier_group",
		)
	frappe.throw(_("Unsupported Simple Supplier search field: {0}").format(fieldname))
	return []


@frappe.whitelist(methods=["POST"])
def create_simple_supplier(values: dict | str | None = None) -> dict[str, Any]:
	_assert_can_create_supplier()
	values = _coerce_values(values)
	supplier_name = str(values.get("supplier_name") or "").strip()
	if not supplier_name:
		frappe.throw(_("Supplier Name is required."))

	supplier_type = str(values.get("supplier_type") or "Company").strip()
	if supplier_type not in {"Company", "Individual"}:
		frappe.throw(_("Supplier Type must be Company or Individual."))

	supplier_group = str(values.get("supplier_group") or _default_supplier_group() or "").strip()
	if not supplier_group:
		frappe.throw(_("Supplier Group is required. Configure an ERPNext default or select one."))
	_assert_read_permission("Supplier Group", supplier_group)
	_validate_leaf_master("Supplier Group", supplier_group)

	doc = frappe.new_doc(SUPPLIER_DOCTYPE)
	doc.supplier_name = supplier_name
	doc.supplier_type = supplier_type
	doc.supplier_group = supplier_group
	meta = frappe.get_meta(SUPPLIER_DOCTYPE)
	for fieldname in ("mobile_no", "email_id", "tax_id"):
		value = str(values.get(fieldname) or "").strip()
		if value and meta.has_field(fieldname):
			setattr(doc, fieldname, value)
	doc.insert()

	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"supplier_name": doc.supplier_name,
		"supplier_type": doc.supplier_type,
		"supplier_group": doc.supplier_group,
		"route": f"/app/supplier/{doc.name}",
	}


def _default_supplier_group() -> str:
	return (
		frappe.defaults.get_user_default("Supplier Group")
		or frappe.db.get_single_value("Buying Settings", "supplier_group")
		or ""
	)


def _validate_leaf_master(doctype: str, name: str) -> None:
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if frappe.db.get_value(doctype, name, "is_group"):
		frappe.throw(_("{0} {1} must be a selectable leaf record.").format(doctype, name))


def _assert_can_create_supplier() -> None:
	if not frappe.has_permission(SUPPLIER_DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Suppliers."), frappe.PermissionError)


def _assert_read_permission(doctype: str, name: str) -> None:
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to use {0} {1}.").format(doctype, name), frappe.PermissionError)


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if isinstance(values, str):
		values = frappe.parse_json(values)
	return dict(values or {})
