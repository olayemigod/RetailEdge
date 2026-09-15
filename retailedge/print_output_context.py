from __future__ import annotations

import base64
import io
from typing import Any

import frappe
from frappe.utils import cint, flt

from retailedge.company_profile import resolve_company_profile


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _active_options() -> dict[str, Any]:
	flags = getattr(frappe, "flags", None)
	if not flags:
		return {}
	return dict(getattr(flags, "retailedge_output_options", None) or {})


def _document_date(doc) -> str:
	for fieldname in ("posting_date", "transaction_date"):
		if doc.meta.has_field(fieldname) and doc.get(fieldname):
			return _clean(doc.get(fieldname))
	return ""


def _qr_payload(doc, company_label: str) -> str:
	parts = [
		f"Company: {company_label or _clean(doc.get('company'))}",
		f"Document: {_clean(doc.doctype)} {_clean(doc.name)}",
	]
	document_date = _document_date(doc)
	if document_date:
		parts.append(f"Date: {document_date}")
	if doc.meta.has_field("currency") and doc.meta.has_field("grand_total"):
		currency = _clean(doc.get("currency"))
		total = flt(doc.get("grand_total"))
		parts.append(f"Total: {currency} {total:.2f}".strip())
	return "\n".join(parts)


def _qr_data_uri(value: str) -> str:
	if not value:
		return ""
	try:
		from frappe.utils.print_format_generator import get_qr_code

		return get_qr_code(value)
	except Exception:
		from pyqrcode import create as qrcreate

		stream = io.BytesIO()
		qrcreate(value).svg(stream, scale=4, quiet_zone=1)
		return "data:image/svg+xml;base64," + base64.b64encode(stream.getvalue()).decode()


def get_retailedge_print_context(doc) -> dict[str, Any]:
	"""Return presentation-only print identity and request-scoped output options.

	The source business document is never changed. Logo/QR choices are supplied
	through request-local Frappe flags by Document Output & Sharing.
	"""
	options = _active_options()
	show_logo = bool(cint(options.get("show_logo", 1)))
	include_qr = bool(cint(options.get("include_qr", 0)))

	company = _clean(doc.get("company")) if doc.meta.has_field("company") else ""
	profile = resolve_company_profile(company) if company else {}
	display_name = _clean(profile.get("label")) or _clean(profile.get("official_name")) or company
	logo = _clean(profile.get("logo")) if show_logo else ""
	website = _clean(profile.get("website"))
	email = _clean(profile.get("email"))
	phone = _clean(profile.get("phone"))
	whatsapp = _clean(profile.get("whatsapp_number"))
	address_parts = [
		_clean(profile.get("address_line1")),
		_clean(profile.get("address_line2")),
		_clean(profile.get("city")),
		_clean(profile.get("county")),
		_clean(profile.get("state")),
		_clean(profile.get("profile_country")) or _clean(profile.get("country")),
		_clean(profile.get("postal_code")),
	]
	address = ", ".join(part for part in address_parts if part)

	qr_payload = _qr_payload(doc, display_name) if include_qr else ""
	return {
		"company": company,
		"display_name": display_name,
		"logo": logo,
		"show_logo": show_logo,
		"include_qr": include_qr,
		"qr_payload": qr_payload,
		"qr_data_uri": _qr_data_uri(qr_payload) if qr_payload else "",
		"website": website,
		"email": email,
		"phone": phone,
		"whatsapp": whatsapp,
		"address": address,
	}
