from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.operating_context import (
	get_allowed_operating_branches,
	get_allowed_operating_contexts,
	get_operating_context,
)


PROFILE_DOCTYPE = "RetailEdge Company Profile"
PROFILE_FIELDS = (
	"display_name",
	"logo",
	"phone",
	"whatsapp_number",
	"email",
	"website",
	"address_line1",
	"address_line2",
	"city",
	"county",
	"state",
	"country",
	"postal_code",
)
ADDRESS_PROFILE_FIELDS = (
	"address_line1",
	"address_line2",
	"city",
	"county",
	"state",
	"country",
	"postal_code",
)
COMPANY_READ_ONLY_FIELDS = (
	"company_name",
	"company_logo",
	"abbr",
	"default_currency",
	"country",
	"tax_id",
	"website",
	"date_of_establishment",
)


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _assert_company_access(company: str) -> None:
	if not company:
		frappe.throw(_("Company is required."))
	get_allowed_operating_contexts(company=company)


def _company_row(company: str) -> dict[str, Any]:
	fallback = {
		"name": company,
		"company_name": company,
		"company_logo": "",
		"abbr": "",
		"default_currency": "",
		"country": "",
		"tax_id": "",
		"website": "",
		"date_of_establishment": "",
	}
	if not company or not frappe.db.exists("Company", company):
		return fallback

	meta = frappe.get_meta("Company")
	fields = ["name", *[fieldname for fieldname in COMPANY_READ_ONLY_FIELDS if meta.has_field(fieldname)]]
	row = frappe.db.get_value("Company", company, fields, as_dict=True) or {}
	fallback.update(row)
	return fallback


def _profile_name(company: str) -> str:
	if not frappe.db.exists("DocType", PROFILE_DOCTYPE):
		return ""
	return _clean(frappe.db.exists(PROFILE_DOCTYPE, {"company": company}) or "")


def _profile_row(company: str) -> dict[str, Any]:
	payload = {fieldname: "" for fieldname in PROFILE_FIELDS}
	name = _profile_name(company)
	payload["profile_docname"] = name
	if not name:
		return payload

	meta = frappe.get_meta(PROFILE_DOCTYPE)
	fields = ["name", "company", *[fieldname for fieldname in PROFILE_FIELDS if meta.has_field(fieldname)]]
	row = frappe.db.get_value(PROFILE_DOCTYPE, name, fields, as_dict=True) or {}
	payload.update(row)
	payload["profile_docname"] = row.get("name") or name
	return payload


def resolve_company_profile(company: str) -> dict[str, Any]:
	"""Merge accounting-safe ERPNext Company truth with RetailEdge presentation profile."""
	company = _clean(company)
	base = _company_row(company)
	product = _profile_row(company)

	company_name = _clean(base.get("company_name")) or _clean(base.get("name")) or company
	display_name = _clean(product.get("display_name")) or company_name
	logo = _clean(product.get("logo")) or _clean(base.get("company_logo"))
	website = _clean(product.get("website")) or _clean(base.get("website"))

	return {
		"name": _clean(base.get("name")) or company,
		"label": display_name,
		"official_name": company_name,
		"display_name": _clean(product.get("display_name")),
		"logo": logo,
		"profile_logo": _clean(product.get("logo")),
		"profile_docname": _clean(product.get("profile_docname")),
		"abbr": _clean(base.get("abbr")),
		"currency": _clean(base.get("default_currency")),
		"country": _clean(base.get("country")),
		"tax_id": _clean(base.get("tax_id")),
		"website": website,
		"company_website": _clean(base.get("website")),
		"date_of_establishment": base.get("date_of_establishment") or "",
		"phone": _clean(product.get("phone")),
		"whatsapp_number": _clean(product.get("whatsapp_number")),
		"email": _clean(product.get("email")),
		"address_line1": _clean(product.get("address_line1")),
		"address_line2": _clean(product.get("address_line2")),
		"city": _clean(product.get("city")),
		"county": _clean(product.get("county")),
		"state": _clean(product.get("state")),
		"profile_country": _clean(product.get("country")),
		"postal_code": _clean(product.get("postal_code")),
	}


def _can_create_profile() -> bool:
	try:
		return bool(frappe.has_permission(PROFILE_DOCTYPE, "create"))
	except Exception:
		return False


def _can_write_profile(profile_name: str = "") -> bool:
	try:
		if profile_name:
			return bool(frappe.has_permission(PROFILE_DOCTYPE, "write", doc=profile_name))
		return _can_create_profile()
	except Exception:
		return False


def _assert_profile_write(company: str, profile_name: str = "") -> None:
	_assert_company_access(company)
	if not _can_write_profile(profile_name):
		frappe.throw(_("You do not have permission to update this Company profile."), frappe.PermissionError)


def _permissions(company: str, profile_name: str = "") -> dict[str, bool]:
	can_write = _can_write_profile(profile_name)
	return {
		"can_write": can_write,
		"can_upload_logo": can_write,
		"can_manage_address": can_write,
	}


def _profile_response(company: str) -> dict[str, Any]:
	current = get_operating_context()
	profile = resolve_company_profile(company)
	return {
		"profile": profile,
		"operating_context": current,
		"permissions": _permissions(company, profile.get("profile_docname") or ""),
		"source_of_truth": "ERPNext Company + RetailEdge Company Profile",
	}


def _new_profile(company: str):
	doc = frappe.new_doc(PROFILE_DOCTYPE)
	doc.company = company
	doc.display_name = _company_row(company).get("company_name") or company
	return doc


def _get_or_new_profile(company: str):
	name = _profile_name(company)
	if name:
		return frappe.get_doc(PROFILE_DOCTYPE, name), False
	return _new_profile(company), True


def _save_profile_doc(doc, *, is_new: bool):
	if is_new:
		doc.insert()
	else:
		doc.save()
	return doc


@frappe.whitelist()
def get_company_profile(company: str = "") -> dict[str, Any]:
	current = get_operating_context()
	company = _clean(company) or _clean(current.get("company"))
	_assert_company_access(company)
	return _profile_response(company)


@frappe.whitelist(methods=["POST"])
def ensure_company_profile(company: str) -> dict[str, Any]:
	company = _clean(company)
	_assert_company_access(company)
	name = _profile_name(company)
	if name:
		return _profile_response(company)
	_assert_profile_write(company)
	doc = _new_profile(company)
	doc.insert()
	return _profile_response(company)


@frappe.whitelist(methods=["POST"])
def save_company_profile(company: str, profile: str | dict[str, Any]) -> dict[str, Any]:
	company = _clean(company)
	payload = frappe.parse_json(profile) if isinstance(profile, str) else dict(profile or {})
	doc, is_new = _get_or_new_profile(company)
	_assert_profile_write(company, "" if is_new else doc.name)

	for fieldname in PROFILE_FIELDS:
		if fieldname not in payload or fieldname in ADDRESS_PROFILE_FIELDS or fieldname == "logo":
			continue
		doc.set(fieldname, _clean(payload.get(fieldname)))
	_save_profile_doc(doc, is_new=is_new)
	return _profile_response(company)


@frappe.whitelist(methods=["POST"])
def save_company_address(company: str, address: str | dict[str, Any]) -> dict[str, Any]:
	company = _clean(company)
	payload = frappe.parse_json(address) if isinstance(address, str) else dict(address or {})
	doc, is_new = _get_or_new_profile(company)
	_assert_profile_write(company, "" if is_new else doc.name)

	for fieldname in ADDRESS_PROFILE_FIELDS:
		if fieldname in payload:
			doc.set(fieldname, _clean(payload.get(fieldname)))
	_save_profile_doc(doc, is_new=is_new)
	return _profile_response(company)


def _assert_attached_profile_logo(profile_name: str, file_url: str) -> None:
	if not file_url:
		return
	file_name = frappe.db.get_value(
		"File",
		{
			"file_url": file_url,
			"attached_to_doctype": PROFILE_DOCTYPE,
			"attached_to_name": profile_name,
		},
		"name",
	)
	if not file_name:
		frappe.throw(_("Upload the logo through this Company Profile before selecting it."))


@frappe.whitelist(methods=["POST"])
def set_company_logo(company: str, file_url: str = "") -> dict[str, Any]:
	company = _clean(company)
	doc, is_new = _get_or_new_profile(company)
	_assert_profile_write(company, "" if is_new else doc.name)
	if is_new:
		_save_profile_doc(doc, is_new=True)
	_assert_attached_profile_logo(doc.name, _clean(file_url))
	doc.reload()
	doc.logo = _clean(file_url)
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
