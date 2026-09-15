from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.operating_context import (
	get_allowed_operating_branches,
	get_allowed_operating_contexts,
	get_operating_context,
)


PROFILE_EDITABLE_FIELDS = (
	"company_name",
	"tax_id",
	"website",
	"date_of_establishment",
)
PROFILE_READ_ONLY_FIELDS = (
	"abbr",
	"default_currency",
	"country",
)
ADDRESS_FIELDS = (
	"address_title",
	"address_type",
	"address_line1",
	"address_line2",
	"city",
	"county",
	"state",
	"country",
	"pincode",
	"phone",
	"email_id",
)


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _company_meta():
	return frappe.get_meta("Company")


def _company_fields() -> list[str]:
	meta = _company_meta()
	fields = ["name"]
	for fieldname in ("company_logo", *PROFILE_EDITABLE_FIELDS, *PROFILE_READ_ONLY_FIELDS):
		if meta.has_field(fieldname):
			fields.append(fieldname)
	return fields


def _profile_from_row(row: dict[str, Any], company: str) -> dict[str, Any]:
	return {
		"name": row.get("name") or company,
		"label": row.get("company_name") or row.get("name") or company,
		"company_name": row.get("company_name") or row.get("name") or company,
		"logo": row.get("company_logo") or "",
		"abbr": row.get("abbr") or "",
		"currency": row.get("default_currency") or "",
		"country": row.get("country") or "",
		"tax_id": row.get("tax_id") or "",
		"website": row.get("website") or "",
		"date_of_establishment": row.get("date_of_establishment") or "",
	}


def resolve_company_profile(company: str) -> dict[str, Any]:
	"""Return presentation-safe ERPNext Company identity without duplicating Company truth."""
	company = _clean(company)
	fallback = {
		"name": company,
		"label": company,
		"company_name": company,
		"logo": "",
		"abbr": "",
		"currency": "",
		"country": "",
		"tax_id": "",
		"website": "",
		"date_of_establishment": "",
	}
	if not company or not frappe.db.exists("Company", company):
		return fallback

	row = frappe.db.get_value("Company", company, _company_fields(), as_dict=True) or {}
	return _profile_from_row(row, company)


def _assert_company_access(company: str) -> None:
	if not company:
		frappe.throw(_("Company is required."))
	# Operating Context is the RetailEdge product authority. This validation also
	# preserves assignment-authoritative users who may not have generic Company read.
	get_allowed_operating_contexts(company=company)


def _assert_company_write(company: str) -> None:
	_assert_company_access(company)
	try:
		allowed = bool(frappe.has_permission("Company", "write", doc=company))
	except Exception:
		allowed = False
	if not allowed:
		frappe.throw(_("You do not have permission to update this Company profile."), frappe.PermissionError)


def _find_company_address(company: str) -> str:
	try:
		return (
			frappe.db.get_value(
				"Dynamic Link",
				{
					"parenttype": "Address",
					"link_doctype": "Company",
					"link_name": company,
				},
				"parent",
				order_by="idx asc",
			)
			or ""
		)
	except Exception:
		return ""


def _address_payload(company: str) -> dict[str, Any]:
	name = _find_company_address(company)
	payload = {fieldname: "" for fieldname in ADDRESS_FIELDS}
	payload.update({"name": name})
	if not name or not frappe.db.exists("Address", name):
		return payload
	meta = frappe.get_meta("Address")
	fields = ["name", *[fieldname for fieldname in ADDRESS_FIELDS if meta.has_field(fieldname)]]
	row = frappe.db.get_value("Address", name, fields, as_dict=True) or {}
	payload.update({fieldname: row.get(fieldname) or "" for fieldname in fields})
	return payload


def _permissions(company: str, address_name: str = "") -> dict[str, bool]:
	try:
		can_write = bool(frappe.has_permission("Company", "write", doc=company))
	except Exception:
		can_write = False
	try:
		can_manage_address = bool(
			frappe.has_permission("Address", "write", doc=address_name)
			if address_name
			else frappe.has_permission("Address", "create")
		)
	except Exception:
		can_manage_address = False
	return {
		"can_write": can_write,
		"can_upload_logo": can_write,
		"can_manage_address": can_manage_address,
	}


def _profile_response(company: str) -> dict[str, Any]:
	current = get_operating_context()
	profile = resolve_company_profile(company)
	address = _address_payload(company)
	return {
		"profile": profile,
		"address": address,
		"operating_context": current,
		"permissions": _permissions(company, address.get("name") or ""),
		"source_of_truth": "ERPNext Company",
	}


@frappe.whitelist()
def get_company_profile(company: str = "") -> dict[str, Any]:
	current = get_operating_context()
	company = _clean(company) or _clean(current.get("company"))
	_assert_company_access(company)
	return _profile_response(company)


@frappe.whitelist(methods=["POST"])
def save_company_profile(company: str, profile: str | dict[str, Any]) -> dict[str, Any]:
	company = _clean(company)
	_assert_company_write(company)
	payload = frappe.parse_json(profile) if isinstance(profile, str) else dict(profile or {})
	doc = frappe.get_doc("Company", company)
	meta = frappe.get_meta("Company")
	for fieldname in PROFILE_EDITABLE_FIELDS:
		if fieldname not in payload or not meta.has_field(fieldname):
			continue
		value = payload.get(fieldname)
		if fieldname == "date_of_establishment":
			doc.set(fieldname, value or None)
		else:
			doc.set(fieldname, _clean(value))
	doc.save()
	return _profile_response(company)


def _assert_address_permission(address_name: str = "") -> None:
	try:
		allowed = bool(
			frappe.has_permission("Address", "write", doc=address_name)
			if address_name
			else frappe.has_permission("Address", "create")
		)
	except Exception:
		allowed = False
	if not allowed:
		frappe.throw(_("You do not have permission to update the Company address."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def save_company_address(company: str, address: str | dict[str, Any]) -> dict[str, Any]:
	company = _clean(company)
	_assert_company_access(company)
	payload = frappe.parse_json(address) if isinstance(address, str) else dict(address or {})
	existing_name = _clean(payload.get("name")) or _find_company_address(company)
	_assert_address_permission(existing_name)

	if existing_name:
		doc = frappe.get_doc("Address", existing_name)
	else:
		doc = frappe.new_doc("Address")
		doc.address_title = _clean(payload.get("address_title")) or resolve_company_profile(company).get("label") or company
		doc.address_type = _clean(payload.get("address_type")) or "Office"
		doc.append("links", {"link_doctype": "Company", "link_name": company})

	meta = frappe.get_meta("Address")
	for fieldname in ADDRESS_FIELDS:
		if not meta.has_field(fieldname) or fieldname not in payload:
			continue
		doc.set(fieldname, _clean(payload.get(fieldname)))
	if not _clean(doc.get("address_title")):
		doc.address_title = resolve_company_profile(company).get("label") or company
	if not _clean(doc.get("address_type")):
		doc.address_type = "Office"
	if not any(
		_clean(row.link_doctype) == "Company" and _clean(row.link_name) == company
		for row in (doc.get("links") or [])
	):
		doc.append("links", {"link_doctype": "Company", "link_name": company})
	doc.save()
	return _profile_response(company)


def _assert_attached_company_logo(company: str, file_url: str) -> None:
	if not file_url:
		return
	file_name = frappe.db.get_value(
		"File",
		{
			"file_url": file_url,
			"attached_to_doctype": "Company",
			"attached_to_name": company,
		},
		"name",
	)
	if not file_name:
		frappe.throw(_("Upload the logo through this Company Profile before selecting it."))


@frappe.whitelist(methods=["POST"])
def set_company_logo(company: str, file_url: str = "") -> dict[str, Any]:
	company = _clean(company)
	_assert_company_write(company)
	file_url = _clean(file_url)
	_assert_attached_company_logo(company, file_url)
	meta = frappe.get_meta("Company")
	if not meta.has_field("company_logo"):
		frappe.throw(_("This ERPNext Company does not expose a Company Logo field."))
	doc = frappe.get_doc("Company", company)
	doc.company_logo = file_url
	doc.save()
	return _profile_response(company)


@frappe.whitelist()
def get_shell_identity() -> dict[str, Any]:
	current = get_operating_context()
	company = _clean(current.get("company"))
	profile = resolve_company_profile(company)
	branches = get_allowed_operating_branches(company=company) if company else []
	return {
		"product_code": "retailedge",
		"product_name": "RetailEdge",
		"product_logo": "",
		"product_icon": "shopping-cart",
		"product_subtitle": "Retail operations & control",
		"tenant_name": profile.get("label") or company,
		"tenant_logo": profile.get("logo") or "",
		"tenant_icon": "building",
		"tenant_subtitle": "Business workspace",
		"active_company": company,
		"active_branch": _clean(current.get("branch")),
		"branch_options": list(branches),
		"can_switch_branch": len(branches) > 1,
		"company_profile": profile,
	}
