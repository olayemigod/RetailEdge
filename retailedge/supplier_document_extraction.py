from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, strip_html

INTERNAL_EXTRACTION_ROLES = {
	"System Manager",
	"Purchase Manager",
	"Purchase User",
	"Accounts Manager",
	"Accounts User",
}
ALLOWED_REVIEW_DECISIONS = {"Accepted", "Rejected"}
FINAL_INTAKE_STATUSES = {"Accepted", "Rejected"}
MAX_TEXT_LENGTH = 140
MAX_REVIEW_NOTES_LENGTH = 2000
MAX_PROVIDER_PAYLOAD_LENGTH = 100000


def _assert_internal_extraction_user() -> str:
	user = str(frappe.session.user or "")
	if not user or user == "Guest":
		frappe.throw(_("Sign in with an internal purchasing or accounts account."), frappe.PermissionError)
	roles = set(frappe.get_roles(user))
	if not roles.intersection(INTERNAL_EXTRACTION_ROLES):
		frappe.throw(_("You do not have permission to review supplier documents."), frappe.PermissionError)
	return user


def _clean_text(value: Any, label: str, *, max_length: int = MAX_TEXT_LENGTH) -> str:
	cleaned = strip_html(str(value or "")).strip()
	if len(cleaned) > max_length:
		frappe.throw(_("{0} cannot exceed {1} characters.").format(label, max_length), frappe.ValidationError)
	return cleaned


def _clean_review_notes(value: Any, *, required: bool = False) -> str:
	cleaned = "\n".join(
		line.strip() for line in strip_html(str(value or "")).splitlines() if line.strip()
	).strip()
	if required and not cleaned:
		frappe.throw(_("Review notes are required when rejecting an extraction."), frappe.ValidationError)
	if len(cleaned) > MAX_REVIEW_NOTES_LENGTH:
		frappe.throw(
			_("Review notes cannot exceed {0} characters.").format(MAX_REVIEW_NOTES_LENGTH),
			frappe.ValidationError,
		)
	return cleaned


def _optional_amount(value: Any) -> float | None:
	if value is None or str(value).strip() == "":
		return None
	return flt(value)


def _optional_date(value: Any):
	if value is None or str(value).strip() == "":
		return None
	try:
		return getdate(value)
	except Exception:
		frappe.throw(_("Enter a valid document date."), frappe.ValidationError)


def _validate_currency(value: Any) -> str:
	currency = _clean_text(value, _("Currency"), max_length=20).upper()
	if currency and not frappe.db.exists("Currency", currency):
		frappe.throw(_("Currency {0} was not found.").format(currency), frappe.DoesNotExistError)
	return currency


def _load_intake(intake_name: str, *, lock: bool = False):
	intake_name = _clean_text(intake_name, _("Supplier Document Intake"))
	if not intake_name or not frappe.db.exists("Supplier Document Intake", intake_name):
		frappe.throw(_("Supplier Document Intake was not found."), frappe.DoesNotExistError)
	if lock:
		frappe.db.sql(
			"select name from `tabSupplier Document Intake` where name=%s for update",
			(intake_name,),
		)
	intake = frappe.get_doc("Supplier Document Intake", intake_name)
	intake.check_permission("read")
	if intake.review_status in FINAL_INTAKE_STATUSES:
		frappe.throw(
			_("Accepted or rejected supplier document intake records cannot receive new extraction evidence."),
			frappe.ValidationError,
		)
	return intake


def _source_file_for_intake(intake):
	rows = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "Supplier Document Intake",
			"attached_to_name": intake.name,
			"file_name": intake.original_file_name,
			"is_private": 1,
		},
		fields=["name", "file_name", "file_url", "is_private", "attached_to_doctype", "attached_to_name"],
		order_by="creation desc",
		limit_page_length=1,
	)
	if not rows:
		frappe.throw(
			_("The private source file attached to this intake could not be found."),
			frappe.DoesNotExistError,
		)
	return rows[0]


def _provider_payload_json(payload: Any) -> str:
	if payload in (None, "", {}, []):
		return ""
	try:
		encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
	except (TypeError, ValueError):
		frappe.throw(_("Provider payload must be JSON serializable."), frappe.ValidationError)
	if len(encoded) > MAX_PROVIDER_PAYLOAD_LENGTH:
		frappe.throw(
			_("Provider payload cannot exceed {0} characters.").format(MAX_PROVIDER_PAYLOAD_LENGTH),
			frappe.ValidationError,
		)
	return encoded


def _create_extraction(
	*,
	intake,
	extraction_method: str,
	document_number: Any = None,
	document_date: Any = None,
	currency: Any = None,
	subtotal: Any = None,
	tax_amount: Any = None,
	total: Any = None,
	purchase_order_reference: Any = None,
	confidence: Any = None,
	provider_name: str = "",
	provider_reference: str = "",
	raw_payload: Any = None,
):
	source_file = _source_file_for_intake(intake)
	method = str(extraction_method or "").strip().title()
	if method not in {"Manual", "Provider"}:
		frappe.throw(_("Choose Manual or Provider extraction."), frappe.ValidationError)

	confidence_value = None
	if confidence is not None and str(confidence).strip() != "":
		confidence_value = flt(confidence)
		if confidence_value < 0 or confidence_value > 100:
			frappe.throw(_("Confidence must be between 0 and 100."), frappe.ValidationError)

	provider = _clean_text(provider_name, _("Provider"))
	provider_ref = _clean_text(provider_reference, _("Provider Reference"))
	payload_json = _provider_payload_json(raw_payload)
	if method == "Manual" and (provider or provider_ref or payload_json or confidence_value is not None):
		frappe.throw(
			_("Manual extraction cannot carry provider metadata or provider confidence."),
			frappe.ValidationError,
		)
	if method == "Provider" and not provider:
		frappe.throw(_("Provider name is required for provider extraction."), frappe.ValidationError)

	extraction = frappe.new_doc("Supplier Document Extraction")
	extraction.update(
		{
			"extraction_key": f"SDE-{uuid4().hex}",
			"supplier_document_intake": intake.name,
			"supplier": intake.supplier,
			"company": intake.company,
			"purchase_order": intake.purchase_order,
			"source_file": source_file.name,
			"source_file_name": source_file.file_name,
			"extraction_method": method,
			"provider_name": provider,
			"provider_reference": provider_ref,
			"extracted_document_number": _clean_text(document_number, _("Document Number")),
			"extracted_document_date": _optional_date(document_date),
			"extracted_currency": _validate_currency(currency),
			"extracted_subtotal": _optional_amount(subtotal),
			"extracted_tax_amount": _optional_amount(tax_amount),
			"extracted_total": _optional_amount(total),
			"extracted_purchase_order_reference": _clean_text(
				purchase_order_reference, _("Purchase Order Reference")
			),
			"confidence": confidence_value,
			"raw_payload_json": payload_json,
			"extracted_by": frappe.session.user,
			"extracted_on": now_datetime(),
		}
	)
	extraction.flags.supplier_document_extraction_api_write = True
	extraction.insert(ignore_permissions=True)
	return extraction


@frappe.whitelist(methods=["POST"])
def record_manual_extraction(
	intake_name: str,
	document_number: Any = None,
	document_date: Any = None,
	currency: Any = None,
	subtotal: Any = None,
	tax_amount: Any = None,
	total: Any = None,
	purchase_order_reference: Any = None,
) -> dict[str, Any]:
	_assert_internal_extraction_user()
	intake = _load_intake(intake_name, lock=True)
	extraction = _create_extraction(
		intake=intake,
		extraction_method="Manual",
		document_number=document_number,
		document_date=document_date,
		currency=currency,
		subtotal=subtotal,
		tax_amount=tax_amount,
		total=total,
		purchase_order_reference=purchase_order_reference,
	)
	return {
		"extraction": extraction.name,
		"intake": intake.name,
		"review_status": "Pending Review",
		"native_buying_document_created": False,
		"accounting_mutated": False,
	}


def record_provider_extraction(
	intake_name: str,
	*,
	provider_name: str,
	suggestions: dict[str, Any] | None = None,
	provider_reference: str = "",
	raw_payload: Any = None,
) -> dict[str, Any]:
	"""Provider-neutral server boundary for future OCR/vision adapters; intentionally not whitelisted."""
	_assert_internal_extraction_user()
	intake = _load_intake(intake_name, lock=True)
	suggestions = dict(suggestions or {})
	extraction = _create_extraction(
		intake=intake,
		extraction_method="Provider",
		document_number=suggestions.get("document_number"),
		document_date=suggestions.get("document_date"),
		currency=suggestions.get("currency"),
		subtotal=suggestions.get("subtotal"),
		tax_amount=suggestions.get("tax_amount"),
		total=suggestions.get("total"),
		purchase_order_reference=suggestions.get("purchase_order_reference"),
		confidence=suggestions.get("confidence"),
		provider_name=provider_name,
		provider_reference=provider_reference,
		raw_payload=raw_payload,
	)
	return {
		"extraction": extraction.name,
		"intake": intake.name,
		"review_status": "Pending Review",
		"native_buying_document_created": False,
		"accounting_mutated": False,
	}


def _load_extraction(extraction_name: str, *, lock: bool = False):
	extraction_name = _clean_text(extraction_name, _("Supplier Document Extraction"))
	if not extraction_name or not frappe.db.exists("Supplier Document Extraction", extraction_name):
		frappe.throw(_("Supplier Document Extraction was not found."), frappe.DoesNotExistError)
	if lock:
		frappe.db.sql(
			"select name from `tabSupplier Document Extraction` where name=%s for update",
			(extraction_name,),
		)
	extraction = frappe.get_doc("Supplier Document Extraction", extraction_name)
	extraction.check_permission("read")
	return extraction


def _existing_review(extraction_name: str):
	rows = frappe.get_all(
		"Supplier Document Extraction Review",
		filters={"extraction": extraction_name},
		fields=["name", "decision", "reviewed_by", "reviewed_on", "review_notes"],
		order_by="reviewed_on desc, creation desc",
		limit_page_length=1,
	)
	return rows[0] if rows else None


@frappe.whitelist(methods=["GET"])
def get_extraction_review_state(extraction_name: str) -> dict[str, Any]:
	_assert_internal_extraction_user()
	extraction = _load_extraction(extraction_name)
	review = _existing_review(extraction.name)
	if not review:
		return {"extraction": extraction.name, "review_status": "Pending Review", "review": None}
	return {
		"extraction": extraction.name,
		"review_status": review.decision,
		"review": review.name,
		"reviewed_by": review.reviewed_by,
		"reviewed_on": review.reviewed_on,
		"review_notes": review.review_notes or "",
	}


@frappe.whitelist(methods=["POST"])
def record_extraction_review(
	extraction_name: str,
	decision: str,
	review_notes: str = "",
) -> dict[str, Any]:
	_assert_internal_extraction_user()
	decision = str(decision or "").strip().title()
	if decision not in ALLOWED_REVIEW_DECISIONS:
		frappe.throw(_("Choose Accepted or Rejected."), frappe.ValidationError)
	extraction = _load_extraction(extraction_name, lock=True)
	if _existing_review(extraction.name):
		frappe.throw(
			_("This extraction already has a final review. Record a new extraction to correct values."),
			frappe.ValidationError,
		)
	notes = _clean_review_notes(review_notes, required=decision == "Rejected")

	review = frappe.new_doc("Supplier Document Extraction Review")
	review.update(
		{
			"review_key": f"SDER-{uuid4().hex}",
			"extraction": extraction.name,
			"supplier_document_intake": extraction.supplier_document_intake,
			"supplier": extraction.supplier,
			"company": extraction.company,
			"decision": decision,
			"reviewed_by": frappe.session.user,
			"reviewed_on": now_datetime(),
			"review_notes": notes,
		}
	)
	review.flags.supplier_document_extraction_review_api_write = True
	review.insert(ignore_permissions=True)
	return {
		"review": review.name,
		"extraction": extraction.name,
		"review_status": decision,
		"native_buying_document_created": False,
		"accounting_mutated": False,
	}
