from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

CUSTOMER_DOCTYPE = "Customer"
MAX_LINK_RESULTS = 20


@frappe.whitelist()
def get_simple_customer_context() -> dict[str, Any]:
	_assert_can_create_customer()
	return {
		"title": _("Simple Customer"),
		"subtitle": _("Create an ERPNext Customer using the common business fields only."),
		"submit_label": _("Create Customer"),
		"full_form_doctype": CUSTOMER_DOCTYPE,
		"defaults": {
			"customer_name": "",
			"customer_type": "Company",
			"customer_group": _default_customer_group(),
			"territory": _default_territory(),
			"mobile_no": "",
			"email_id": "",
			"tax_id": "",
		},
		"options": {"customer_types": ["Company", "Individual"]},
		"limits": {"link_results": MAX_LINK_RESULTS},
		"capabilities": {"native_form_fallback": True},
	}


@frappe.whitelist()
def search_simple_customer_options(
	fieldname: str,
	txt: str = "",
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_can_create_customer()
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	if fieldname == "customer_group":
		return search_link(
			"Customer Group",
			txt or "",
			filters={"is_group": 0},
			page_length=limit,
			reference_doctype=CUSTOMER_DOCTYPE,
			link_fieldname="customer_group",
		)
	if fieldname == "territory":
		return search_link(
			"Territory",
			txt or "",
			filters={"is_group": 0},
			page_length=limit,
			reference_doctype=CUSTOMER_DOCTYPE,
			link_fieldname="territory",
		)
	frappe.throw(_("Unsupported Simple Customer search field: {0}").format(fieldname))
	return []


@frappe.whitelist(methods=["POST"])
def create_simple_customer(values: dict | str | None = None) -> dict[str, Any]:
	_assert_can_create_customer()
	values = _coerce_values(values)
	customer_name = str(values.get("customer_name") or "").strip()
	if not customer_name:
		frappe.throw(_("Customer Name is required."))

	customer_type = str(values.get("customer_type") or "Company").strip()
	if customer_type not in {"Company", "Individual"}:
		frappe.throw(_("Customer Type must be Company or Individual."))

	customer_group = str(values.get("customer_group") or _default_customer_group() or "").strip()
	territory = str(values.get("territory") or _default_territory() or "").strip()
	if not customer_group:
		frappe.throw(_("Customer Group is required. Configure an ERPNext default or select one."))
	if not territory:
		frappe.throw(_("Territory is required. Configure an ERPNext default or select one."))
	_assert_read_permission("Customer Group", customer_group)
	_assert_read_permission("Territory", territory)
	_validate_leaf_master("Customer Group", customer_group)
	_validate_leaf_master("Territory", territory)

	doc = frappe.new_doc(CUSTOMER_DOCTYPE)
	doc.customer_name = customer_name
	doc.customer_type = customer_type
	doc.customer_group = customer_group
	doc.territory = territory
	for fieldname in ("mobile_no", "email_id", "tax_id"):
		value = str(values.get(fieldname) or "").strip()
		if value and frappe.get_meta(CUSTOMER_DOCTYPE).has_field(fieldname):
			setattr(doc, fieldname, value)
	doc.insert()

	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"customer_name": doc.customer_name,
		"customer_type": doc.customer_type,
		"customer_group": doc.customer_group,
		"territory": doc.territory,
		"route": f"/app/customer/{doc.name}",
	}


def _default_customer_group() -> str:
	return (
		frappe.defaults.get_user_default("Customer Group")
		or frappe.db.get_single_value("Selling Settings", "customer_group")
		or ""
	)


def _default_territory() -> str:
	return (
		frappe.defaults.get_user_default("Territory")
		or frappe.db.get_single_value("Selling Settings", "territory")
		or ""
	)


def _validate_leaf_master(doctype: str, name: str) -> None:
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if frappe.db.get_value(doctype, name, "is_group"):
		frappe.throw(_("{0} {1} must be a selectable leaf record.").format(doctype, name))


def _assert_can_create_customer() -> None:
	if not frappe.has_permission(CUSTOMER_DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Customers."), frappe.PermissionError)


def _assert_read_permission(doctype: str, name: str) -> None:
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to use {0} {1}.").format(doctype, name), frappe.PermissionError)


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if isinstance(values, str):
		values = frappe.parse_json(values)
	return dict(values or {})
