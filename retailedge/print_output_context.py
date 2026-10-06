from __future__ import annotations

import base64
import io
from typing import Any

import frappe
from frappe.utils import cint, flt

from retailedge.branch_context import BRANCH_FIELD_CANDIDATES
from retailedge.branch_profile import get_exact_branch_profile
from retailedge.company_profile import resolve_company_profile
from retailedge.print_output_settings import BRANCH_PRINT_VISIBILITY_FIELD


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


def _document_branch(doc) -> str:
	for fieldname in BRANCH_FIELD_CANDIDATES:
		if not doc.meta.has_field(fieldname):
			continue
		branch = _clean(doc.get(fieldname))
		if branch:
			return branch
	return ""


def _show_branch_on_printed_documents(company: str, branch: str) -> bool:
	if not company or not branch:
		return False
	try:
		profile = get_exact_branch_profile(company=company, branch=branch, active_only=True)
	except Exception:
		return False
	if not profile or not profile.meta.has_field(BRANCH_PRINT_VISIBILITY_FIELD):
		return False
	return bool(cint(profile.get(BRANCH_PRINT_VISIBILITY_FIELD)))


def _business_address(profile: dict[str, Any]) -> str:
	candidates = [
		_clean(profile.get("address_line1")),
		_clean(profile.get("address_line2")),
		_clean(profile.get("city")),
		_clean(profile.get("county")),
		_clean(profile.get("state")),
		_clean(profile.get("profile_country")) or _clean(profile.get("country")),
		_clean(profile.get("postal_code")),
	]
	parts: list[str] = []
	canonical_parts: list[str] = []
	for raw in candidates:
		part = raw.strip(" ,")
		if not part:
			continue
		canonical = " ".join(part.lower().replace(",", " ").split())
		if any(canonical == previous or canonical in previous for previous in canonical_parts):
			continue
		parts.append(part)
		canonical_parts.append(canonical)
	return ", ".join(parts)


def get_business_document_qr_payload(doc, company_label: str = "") -> str:
	"""Return the canonical PEdge document-reference QR payload.

	Document/PDF output and direct thermal receipt printing use the same
	presentation-only payload. The source business document is never changed.
	"""
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


def _qr_payload(doc, company_label: str) -> str:
	# Backward-compatible internal alias for older callers/tests.
	return get_business_document_qr_payload(doc, company_label)


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


def get_business_print_context(doc) -> dict[str, Any]:
	"""Return presentation-only print identity and request-scoped output options.

	The source business document is never changed. Logo/QR choices are supplied
	through request-local Frappe flags by Document Output & Sharing. Branch display
	is governed by the exact Company + Branch RetailEdge Branch Profile.
	"""
	options = _active_options()
	show_logo = bool(cint(options.get("show_logo", 1)))
	include_qr = bool(cint(options.get("include_qr", 0)))

	company = _clean(doc.get("company")) if doc.meta.has_field("company") else ""
	branch = _document_branch(doc)
	show_branch = _show_branch_on_printed_documents(company, branch)
	profile = resolve_company_profile(company) if company else {}
	display_name = _clean(profile.get("label")) or _clean(profile.get("official_name")) or company
	logo = _clean(profile.get("logo")) if show_logo else ""
	website = _clean(profile.get("website"))
	email = _clean(profile.get("email"))
	phone = _clean(profile.get("phone"))
	whatsapp = _clean(profile.get("whatsapp_number"))
	address = _business_address(profile)

	qr_payload = get_business_document_qr_payload(doc, display_name) if include_qr else ""
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
		"show_branch": show_branch,
		"branch": branch if show_branch else "",
	}
