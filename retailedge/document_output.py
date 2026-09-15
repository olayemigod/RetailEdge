from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from urllib.parse import quote

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.utils import cint, flt, validate_email_address
from frappe.utils.user import get_user_fullname

from retailedge.branch_context import BRANCH_FIELD_CANDIDATES, get_first_existing_field
from retailedge.operating_context import get_operating_context
from retailedge.professional_print_formats import (
	MANAGED_PRINT_FORMATS,
	is_managed_print_format_html,
	get_preferred_print_format,
)

MAX_LINK_RESULTS = 20
MAX_PRINT_FORMATS = 50


def _managed_format_names(doctype: str) -> list[str]:
	return [
		str(spec.get("name") or "").strip()
		for spec in MANAGED_PRINT_FORMATS
		if spec.get("doctype") == doctype and str(spec.get("name") or "").strip()
	]


def _outgoing_email_ready() -> bool:
	try:
		return bool(EmailAccount.find_default_outgoing())
	except Exception:
		return False


@contextmanager
def _output_render_options(*, show_logo: int = 1, include_qr: int = 0):
	previous = getattr(frappe.flags, "retailedge_output_options", None)
	frappe.flags.retailedge_output_options = {
		"show_logo": cint(show_logo),
		"include_qr": cint(include_qr),
	}
	try:
		yield
	finally:
		frappe.flags.retailedge_output_options = previous


def _render_document(
	doctype: str,
	name: str,
	*,
	print_format: str,
	no_letterhead: int = 1,
	show_logo: int = 1,
	include_qr: int = 0,
	as_pdf: bool = False,
):
	with _output_render_options(show_logo=show_logo, include_qr=include_qr):
		return frappe.get_print(
			doctype,
			name,
			print_format=print_format,
			as_pdf=as_pdf,
			no_letterhead=cint(no_letterhead),
		)


OUTPUT_DOCUMENTS: tuple[dict[str, Any], ...] = (
	{
		"key": "quotation",
		"doctype": "Quotation",
		"label": "Quotation",
		"party_field": "party_name",
		"date_field": "transaction_date",
		"native_route": "/app/quotation",
	},
	{
		"key": "sales-order",
		"doctype": "Sales Order",
		"label": "Sales Order",
		"party_field": "customer",
		"date_field": "transaction_date",
		"native_route": "/app/sales-order",
	},
	{
		"key": "delivery-note",
		"doctype": "Delivery Note",
		"label": "Delivery Note",
		"party_field": "customer",
		"date_field": "posting_date",
		"native_route": "/app/delivery-note",
	},
	{
		"key": "sales-invoice",
		"doctype": "Sales Invoice",
		"label": "Sales Invoice",
		"party_field": "customer",
		"date_field": "posting_date",
		"native_route": "/app/sales-invoice",
	},
	{
		"key": "pos-receipt",
		"doctype": "POS Invoice",
		"label": "POS Receipt",
		"party_field": "customer",
		"date_field": "posting_date",
		"native_route": "/app/pos-invoice",
	},
)

_DOCUMENT_BY_KEY = {row["key"]: row for row in OUTPUT_DOCUMENTS}
_DOCUMENT_BY_DOCTYPE = {row["doctype"]: row for row in OUTPUT_DOCUMENTS}


def _preferred_print_format(doctype: str) -> str:
	if str(doctype or "").strip() == "POS Invoice":
		return "POS Receipt 80mm"
	return get_preferred_print_format(doctype)


def get_output_document_definition(value: str) -> dict[str, Any]:
	key = str(value or "").strip()
	definition = _DOCUMENT_BY_KEY.get(key) or _DOCUMENT_BY_DOCTYPE.get(key)
	if not definition:
		frappe.throw(_("Unsupported document output type: {0}").format(key))
	return dict(definition)


def _doctype_available(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype))


def _permission(doctype: str, ptype: str, *, name: str | None = None) -> bool:
	try:
		if name:
			return bool(_doctype_available(doctype) and frappe.has_permission(doctype, ptype, doc=name))
		return bool(_doctype_available(doctype) and frappe.has_permission(doctype, ptype))
	except Exception:
		return False


def _assert_document_permission(doctype: str, name: str, ptype: str = "read") -> None:
	name = str(name or "").strip()
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} is not available.").format(doctype, name))
	if not _permission(doctype, ptype, name=name):
		frappe.throw(
			_("You do not have {0} permission for {1} {2}.").format(ptype, doctype, name),
			frappe.PermissionError,
		)


def _document_capability(definition: dict[str, Any]) -> dict[str, Any]:
	doctype = definition["doctype"]
	return {
		**definition,
		"available": _doctype_available(doctype),
		"can_read": _permission(doctype, "read"),
		"can_print": _permission(doctype, "print"),
		"can_email": _permission(doctype, "email"),
		"recommended_print_format": _preferred_print_format(doctype),
	}


def _operating_filters(doctype: str) -> dict[str, Any]:
	operating = get_operating_context() or {}
	company = str(operating.get("company") or "").strip()
	branch = str(operating.get("branch") or "").strip()
	meta = frappe.get_meta(doctype)
	filters: dict[str, Any] = {}
	if company and meta.has_field("company"):
		filters["company"] = company
	if branch:
		branch_field = get_first_existing_field(doctype, BRANCH_FIELD_CANDIDATES)
		if branch_field:
			filters[branch_field] = branch
	return filters


def _validate_print_format(doctype: str, print_format: str | None) -> str:
	print_format = str(print_format or "Standard").strip() or "Standard"
	if print_format == "Standard":
		return print_format
	if not frappe.db.exists("Print Format", print_format):
		frappe.throw(_("Print Format {0} is not available.").format(print_format))
	row = frappe.db.get_value(
		"Print Format", print_format, ["doc_type", "disabled", "html"], as_dict=True
	) or {}
	if str(row.get("doc_type") or "") != doctype:
		frappe.throw(_("Print Format {0} is not for {1}.").format(print_format, doctype))
	if cint(row.get("disabled")):
		frappe.throw(_("Print Format {0} is disabled.").format(print_format))
	managed = is_managed_print_format_html(row.get("html"))
	if not managed and not _permission("Print Format", "read", name=print_format):
		frappe.throw(
			_("You do not have permission to use Print Format {0}.").format(print_format),
			frappe.PermissionError,
		)
	return print_format


def _available_print_formats(doctype: str) -> list[str]:
	formats = ["Standard"]

	# App-managed customer-safe formats are selectable based on permission to print
	# the source document; direct Print Format DocType access is not required.
	for spec in MANAGED_PRINT_FORMATS:
		if spec.get("doctype") != doctype:
			continue
		name = str(spec.get("name") or "").strip()
		if not name or not frappe.db.exists("Print Format", name):
			continue
		row = frappe.db.get_value("Print Format", name, ["disabled", "html"], as_dict=True) or {}
		if not cint(row.get("disabled")) and is_managed_print_format_html(row.get("html")) and name not in formats:
			formats.append(name)

	# Other ERPNext/customer-defined formats remain permission-gated.
	if _permission("Print Format", "read"):
		rows = frappe.get_list(
			"Print Format",
			filters={"doc_type": doctype, "disabled": 0},
			fields=["name"],
			order_by="name asc",
			limit_page_length=MAX_PRINT_FORMATS,
		)
		for row in rows:
			name = str(row.get("name") or "").strip()
			if name and name not in formats:
				formats.append(name)

	preferred = _preferred_print_format(doctype)
	if preferred and preferred in formats:
		formats.remove(preferred)
		formats.insert(0, preferred)
	return formats


def _document_summary(definition: dict[str, Any], doc) -> dict[str, Any]:
	branch = ""
	for fieldname in BRANCH_FIELD_CANDIDATES:
		if doc.meta.has_field(fieldname):
			branch = str(doc.get(fieldname) or "").strip()
			if branch:
				break
	return {
		"doctype": definition["doctype"],
		"document_key": definition["key"],
		"name": doc.name,
		"party": doc.get(definition["party_field"]) or "",
		"date": doc.get(definition["date_field"]) or "",
		"company": doc.get("company") if doc.meta.has_field("company") else "",
		"branch": branch,
		"status": doc.get("status") if doc.meta.has_field("status") else "",
		"docstatus": cint(doc.docstatus),
		"currency": doc.get("currency") if doc.meta.has_field("currency") else "",
		"grand_total": flt(doc.get("grand_total")) if doc.meta.has_field("grand_total") else 0,
		"contact_email": doc.get("contact_email") if doc.meta.has_field("contact_email") else "",
		"contact_mobile": doc.get("contact_mobile") if doc.meta.has_field("contact_mobile") else "",
	}


def _default_share_copy(definition: dict[str, Any], summary: dict[str, Any]) -> dict[str, str]:
	"""Create neutral customer-facing defaults from the client Company identity."""
	company = str(summary.get("company") or "").strip()
	label = str(definition.get("label") or definition.get("doctype") or "Document").strip()
	name = str(summary.get("name") or "").strip()
	identity = company or _("Your supplier")
	subject = _("{0} {1} from {2}").format(label, name, identity)
	message = _("Please find attached {0} {1} from {2}.").format(label, name, identity)
	return {"subject": subject, "message": message, "company": company}


@frappe.whitelist()
def get_document_output_context() -> dict[str, Any]:
	operating = get_operating_context() or {}
	return {
		"operating": {
			"company": operating.get("company") or "",
			"branch": operating.get("branch") or "",
		},
		"documents": [_document_capability(row) for row in OUTPUT_DOCUMENTS],
		"policy": {
			"print_engine": "erpnext_native",
			"print_formats": "erpnext_native",
			"professional_formats": "managed_optional",
			"letterhead": "erpnext_native",
			"email_transport": "frappe_native",
			"whatsapp": "user_initiated_handoff",
			"visible_identity": "document_company_and_letterhead",
			"public_pdf_links": False,
			"business_documents_immutable": True,
		},
		"user_name": get_user_fullname(frappe.session.user) if getattr(frappe, "session", None) else "",
	}


@frappe.whitelist()
def search_output_documents(document: str, txt: str = "", limit: int = MAX_LINK_RESULTS) -> list[dict[str, Any]]:
	definition = get_output_document_definition(document)
	doctype = definition["doctype"]
	if not _permission(doctype, "read"):
		frappe.throw(_("You do not have permission to view {0}.").format(doctype), frappe.PermissionError)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	return search_link(
		doctype,
		txt or "",
		filters=_operating_filters(doctype),
		page_length=limit,
		reference_doctype=doctype,
	)


@frappe.whitelist()
def get_output_document_details(document: str, name: str) -> dict[str, Any]:
	definition = get_output_document_definition(document)
	doctype = definition["doctype"]
	_assert_document_permission(doctype, name, "read")
	doc = frappe.get_doc(doctype, name)
	formats = _available_print_formats(doctype)
	preferred = _preferred_print_format(doctype)
	summary = _document_summary(definition, doc)
	share_copy = _default_share_copy(definition, summary)
	summary.update(
		{
			"can_print": _permission(doctype, "print", name=name),
			"can_email": _permission(doctype, "email", name=name),
			"can_write": _permission(doctype, "write", name=name),
			"email_configured": _outgoing_email_ready(),
			"print_formats": formats,
			"managed_print_formats": _managed_format_names(doctype),
			"recommended_print_format": preferred if preferred in formats else "Standard",
			"default_use_letterhead": False,
			"default_show_logo": True,
			"default_include_qr": False,
			"default_email_subject": share_copy["subject"],
			"default_email_message": share_copy["message"],
			"native_route": f"{definition['native_route']}/{quote(str(name), safe='')}",
		}
	)
	return summary


@frappe.whitelist(methods=["GET"])
def render_document_preview(
	document: str,
	name: str,
	print_format: str = "Standard",
	no_letterhead: int = 1,
	show_logo: int = 1,
	include_qr: int = 0,
) -> dict[str, Any]:
	definition = get_output_document_definition(document)
	doctype = definition["doctype"]
	_assert_document_permission(doctype, name, "read")
	_assert_document_permission(doctype, name, "print")
	print_format = _validate_print_format(doctype, print_format)
	html = _render_document(
		doctype,
		name,
		print_format=print_format,
		as_pdf=False,
		no_letterhead=no_letterhead,
		show_logo=show_logo,
		include_qr=include_qr,
	)
	return {
		"html": html,
		"print_format": print_format,
		"no_letterhead": cint(no_letterhead),
		"show_logo": cint(show_logo),
		"include_qr": cint(include_qr),
	}


@frappe.whitelist(methods=["GET"])
def download_document_pdf(
	document: str,
	name: str,
	print_format: str = "Standard",
	no_letterhead: int = 1,
	show_logo: int = 1,
	include_qr: int = 0,
):
	definition = get_output_document_definition(document)
	doctype = definition["doctype"]
	_assert_document_permission(doctype, name, "read")
	_assert_document_permission(doctype, name, "print")
	print_format = _validate_print_format(doctype, print_format)
	pdf = _render_document(
		doctype,
		name,
		print_format=print_format,
		as_pdf=True,
		no_letterhead=no_letterhead,
		show_logo=show_logo,
		include_qr=include_qr,
	)
	frappe.local.response.filename = f"{doctype}-{name}.pdf"
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "download"


@frappe.whitelist(methods=["POST"])
def send_document_email(
	document: str,
	name: str,
	recipient: str,
	subject: str = "",
	message: str = "",
	print_format: str = "Standard",
	no_letterhead: int = 1,
	show_logo: int = 1,
	include_qr: int = 0,
) -> dict[str, Any]:
	definition = get_output_document_definition(document)
	doctype = definition["doctype"]
	_assert_document_permission(doctype, name, "read")
	_assert_document_permission(doctype, name, "print")
	_assert_document_permission(doctype, name, "email")
	if not _outgoing_email_ready():
		frappe.throw(
			_("Outgoing email is not configured. Configure a default outgoing Email Account before sending documents."),
			frappe.OutgoingEmailError,
		)
	print_format = _validate_print_format(doctype, print_format)
	recipient = str(recipient or "").strip()
	validate_email_address(recipient, throw=True)
	doc = frappe.get_doc(doctype, name)
	summary = _document_summary(definition, doc)
	share_copy = _default_share_copy(definition, summary)
	subject = str(subject or share_copy["subject"]).strip()
	message = str(message or share_copy["message"]).strip()
	pdf = _render_document(
		doctype,
		name,
		print_format=print_format,
		as_pdf=True,
		no_letterhead=no_letterhead,
		show_logo=show_logo,
		include_qr=include_qr,
	)
	frappe.sendmail(
		recipients=[recipient],
		subject=subject,
		message=message,
		attachments=[{"fname": f"{doctype}-{name}.pdf", "fcontent": pdf}],
		reference_doctype=doctype,
		reference_name=name,
	)
	return {
		"queued": True,
		"recipient": recipient,
		"doctype": doctype,
		"name": name,
		"company": summary.get("company") or "",
		"party": summary.get("party") or "",
	}


@frappe.whitelist()
def get_whatsapp_handoff(document: str, name: str) -> dict[str, Any]:
	definition = get_output_document_definition(document)
	doctype = definition["doctype"]
	_assert_document_permission(doctype, name, "read")
	doc = frappe.get_doc(doctype, name)
	summary = _document_summary(definition, doc)
	company = str(summary.get("company") or "").strip()
	amount = ""
	if summary.get("grand_total"):
		amount = f" — {summary.get('currency') or ''} {summary['grand_total']:,.2f}".strip()
	identity = company or _("Your supplier")
	text = _("{0} {1}{2} from {3}. The PDF can be attached from the secure document download.").format(
		definition["label"],
		name,
		amount,
		identity,
	)
	return {
		"text": text,
		"company": company,
		"phone": summary.get("contact_mobile") or "",
		"requires_manual_attachment": True,
		"public_pdf_link": False,
	}
