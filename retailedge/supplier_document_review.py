from __future__ import annotations

from typing import Any
from uuid import uuid4

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt, getdate, now_datetime, strip_html

from erpnext.buying.doctype.purchase_order.mapper import make_purchase_invoice

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	get_user_allowed_branches,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.stock_movement_filters import branch_query

INTERNAL_REVIEW_ROLES = {
	"System Manager",
	"Purchase Manager",
	"Purchase User",
	"Accounts Manager",
	"Accounts User",
}
MAX_QUEUE_ROWS = 100
MAX_LINK_RESULTS = 20
MAX_REVIEW_NOTES_LENGTH = 2000
ALLOWED_INTAKE_REVIEW_STATUSES = {"In Review", "Accepted", "Rejected"}


def _assert_internal_review_user() -> str:
	user = str(frappe.session.user or "")
	if not user or user == "Guest":
		frappe.throw(_("Sign in with an internal purchasing or accounts account."), frappe.PermissionError)
	if not set(frappe.get_roles(user)).intersection(INTERNAL_REVIEW_ROLES):
		frappe.throw(_("You do not have permission to review supplier documents."), frappe.PermissionError)
	return user


def _clean_notes(value: Any, *, required: bool = False) -> str:
	cleaned = "\n".join(
		line.strip() for line in strip_html(str(value or "")).splitlines() if line.strip()
	).strip()
	if required and not cleaned:
		frappe.throw(_("Review notes are required when rejecting a supplier document."), frappe.ValidationError)
	if len(cleaned) > MAX_REVIEW_NOTES_LENGTH:
		frappe.throw(
			_("Review notes cannot exceed {0} characters.").format(MAX_REVIEW_NOTES_LENGTH),
			frappe.ValidationError,
		)
	return cleaned


def _assert_company_read(company: str) -> None:
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("Company was not found."), frappe.DoesNotExistError)
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have access to Company {0}.").format(company), frappe.PermissionError)


def _purchase_order_branch_field() -> str | None:
	return get_first_existing_field("Purchase Order", BRANCH_FIELD_CANDIDATES)


def _purchase_invoice_branch_field() -> str | None:
	return get_first_existing_field("Purchase Invoice", BRANCH_FIELD_CANDIDATES)


def _allowed_branch_names(*, user: str, company: str) -> set[str] | None:
	if user_has_global_branch_access(user=user):
		return None
	return set(get_user_allowed_branches(user=user, company=company).get("branches") or [])


def _latest_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
	result: dict[str, dict[str, Any]] = {}
	for row in rows:
		value = str(row.get(key) or "")
		if value and value not in result:
			result[value] = row
	return result


def _get_private_file_url(file_name: str) -> str:
	if not file_name:
		return ""
	row = frappe.db.get_value("File", file_name, ["file_url", "is_private"], as_dict=True)
	if not row or not int(row.is_private or 0):
		return ""
	return str(row.file_url or "")


@frappe.whitelist(methods=["GET"])
def get_supplier_document_review_context(
	company: str = "",
	branch: str = "",
	supplier: str = "",
	status: str = "Open",
	limit: int = MAX_QUEUE_ROWS,
) -> dict[str, Any]:
	user = _assert_internal_review_user()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(branch or "").strip()
	supplier = str(supplier or "").strip()
	status = str(status or "Open").strip().title()
	limit = max(1, min(cint(limit) or MAX_QUEUE_ROWS, MAX_QUEUE_ROWS))

	if company:
		_assert_company_read(company)
	if branch:
		validate_user_branch_access(branch, user=user, company=company or None, throw=True)

	filters: dict[str, Any] = {}
	if company:
		filters["company"] = company
	if supplier:
		filters["supplier"] = supplier
	if status == "Open":
		filters["review_status"] = ["in", ["Pending Review", "In Review"]]
	elif status in {"Pending Review", "In Review", "Accepted", "Rejected"}:
		filters["review_status"] = status
	elif status not in {"All", ""}:
		frappe.throw(_("Choose Open, Pending Review, In Review, Accepted, Rejected or All."), frappe.ValidationError)

	intakes = frappe.get_list(
		"Supplier Document Intake",
		filters=filters,
		fields=[
			"name",
			"supplier",
			"company",
			"purchase_order",
			"document_type",
			"submitted_on",
			"portal_user",
			"notes",
			"original_file_name",
			"review_status",
			"reviewed_by",
			"reviewed_on",
			"review_notes",
		],
		order_by="submitted_on desc, creation desc",
		limit_page_length=limit,
	)
	if not intakes:
		return _review_context_payload(company=company, branch=branch, user=user, rows=[])

	intake_names = [row.name for row in intakes]
	po_names = list({row.purchase_order for row in intakes if row.purchase_order})
	po_branch_field = _purchase_order_branch_field()
	po_fields = ["name", "supplier", "company", "docstatus", "status", "transaction_date", "currency", "grand_total"]
	if po_branch_field:
		po_fields.append(po_branch_field)
	purchase_orders = frappe.get_list(
		"Purchase Order",
		filters={"name": ["in", po_names]},
		fields=po_fields,
		limit_page_length=max(len(po_names), 1),
	)
	po_by_name = {row.name: row for row in purchase_orders}

	extraction_rows = frappe.get_list(
		"Supplier Document Extraction",
		filters={"supplier_document_intake": ["in", intake_names]},
		fields=[
			"name",
			"supplier_document_intake",
			"supplier",
			"company",
			"purchase_order",
			"source_file",
			"source_file_name",
			"extraction_method",
			"extracted_document_number",
			"extracted_document_date",
			"extracted_currency",
			"extracted_subtotal",
			"extracted_tax_amount",
			"extracted_total",
			"extracted_purchase_order_reference",
			"confidence",
			"extracted_by",
			"extracted_on",
		],
		order_by="extracted_on desc, creation desc",
		limit_page_length=max(len(intake_names) * 5, 1),
	)
	latest_extraction = _latest_by([dict(row) for row in extraction_rows], "supplier_document_intake")
	extraction_names = [row["name"] for row in latest_extraction.values()]

	review_by_extraction: dict[str, dict[str, Any]] = {}
	if extraction_names:
		review_rows = frappe.get_list(
			"Supplier Document Extraction Review",
			filters={"extraction": ["in", extraction_names]},
			fields=["name", "extraction", "decision", "reviewed_by", "reviewed_on", "review_notes"],
			order_by="reviewed_on desc, creation desc",
			limit_page_length=max(len(extraction_names) * 2, 1),
		)
		review_by_extraction = _latest_by([dict(row) for row in review_rows], "extraction")

	handoff_by_extraction: dict[str, dict[str, Any]] = {}
	if extraction_names and frappe.db.exists("DocType", "Supplier Document Purchase Invoice Handoff"):
		handoff_rows = frappe.get_list(
			"Supplier Document Purchase Invoice Handoff",
			filters={"extraction": ["in", extraction_names]},
			fields=[
				"name",
				"extraction",
				"purchase_invoice",
				"created_by",
				"created_on",
				"mapped_grand_total",
				"mapped_currency",
				"extracted_total",
				"total_difference",
			],
			order_by="created_on desc, creation desc",
			limit_page_length=max(len(extraction_names), 1),
		)
		handoff_by_extraction = _latest_by([dict(row) for row in handoff_rows], "extraction")

	rows: list[dict[str, Any]] = []
	allowed_cache: dict[str, set[str] | None] = {}
	for intake in intakes:
		po = po_by_name.get(intake.purchase_order)
		if not po:
			continue
		po_branch = str(po.get(po_branch_field) or "") if po_branch_field else ""
		company_name = str(intake.company or "")
		if company_name not in allowed_cache:
			allowed_cache[company_name] = _allowed_branch_names(user=user, company=company_name)
		allowed = allowed_cache[company_name]
		if branch and po_branch != branch:
			continue
		if allowed is not None and (not po_branch or po_branch not in allowed):
			continue

		extraction = latest_extraction.get(intake.name)
		review = review_by_extraction.get(extraction["name"]) if extraction else None
		handoff = handoff_by_extraction.get(extraction["name"]) if extraction else None
		extraction_decision = str(review.get("decision") or "") if review else "Pending Review"
		ready = bool(
			intake.document_type == "Supplier Invoice"
			and intake.review_status == "Accepted"
			and extraction
			and extraction_decision == "Accepted"
			and not handoff
			and int(po.docstatus or 0) == 1
		)
		rows.append(
			{
				"intake": intake.name,
				"supplier": intake.supplier,
				"company": intake.company,
				"branch": po_branch,
				"purchase_order": intake.purchase_order,
				"purchase_order_status": po.status or "",
				"purchase_order_date": po.transaction_date,
				"purchase_order_currency": po.currency or "",
				"purchase_order_total": po.grand_total,
				"document_type": intake.document_type,
				"submitted_on": intake.submitted_on,
				"portal_user": intake.portal_user,
				"supplier_notes": intake.notes or "",
				"original_file_name": intake.original_file_name,
				"intake_review_status": intake.review_status,
				"intake_review_notes": intake.review_notes or "",
				"extraction": extraction["name"] if extraction else "",
				"extraction_method": extraction.get("extraction_method") if extraction else "",
				"source_file": extraction.get("source_file") if extraction else "",
				"source_file_url": _get_private_file_url(extraction.get("source_file") if extraction else ""),
				"extracted_document_number": extraction.get("extracted_document_number") if extraction else "",
				"extracted_document_date": extraction.get("extracted_document_date") if extraction else None,
				"extracted_currency": extraction.get("extracted_currency") if extraction else "",
				"extracted_subtotal": extraction.get("extracted_subtotal") if extraction else None,
				"extracted_tax_amount": extraction.get("extracted_tax_amount") if extraction else None,
				"extracted_total": extraction.get("extracted_total") if extraction else None,
				"extracted_purchase_order_reference": extraction.get("extracted_purchase_order_reference") if extraction else "",
				"confidence": extraction.get("confidence") if extraction else None,
				"extraction_review_status": extraction_decision,
				"extraction_review": review.get("name") if review else "",
				"extraction_review_notes": review.get("review_notes") if review else "",
				"handoff": handoff.get("name") if handoff else "",
				"purchase_invoice": handoff.get("purchase_invoice") if handoff else "",
				"mapped_grand_total": handoff.get("mapped_grand_total") if handoff else None,
				"total_difference": handoff.get("total_difference") if handoff else None,
				"ready_for_draft_purchase_invoice": ready,
			}
		)

	return _review_context_payload(company=company, branch=branch, user=user, rows=rows)


def _review_context_payload(*, company: str, branch: str, user: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
	return {
		"default_filters": {"company": company, "branch": branch, "status": "Open"},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", user, "full_name") or user,
		"rows": rows,
		"summary": {
			"open": sum(1 for row in rows if row["intake_review_status"] in {"Pending Review", "In Review"}),
			"pending_extraction": sum(1 for row in rows if not row["extraction"]),
			"pending_extraction_review": sum(1 for row in rows if row["extraction"] and row["extraction_review_status"] == "Pending Review"),
			"ready_for_invoice": sum(1 for row in rows if row["ready_for_draft_purchase_invoice"]),
			"drafts_prepared": sum(1 for row in rows if row["purchase_invoice"]),
		},
		"source_of_truth": "ERPNext Purchase Order and Purchase Invoice; supplier extraction values are advisory evidence",
		"draft_only": True,
	}


@frappe.whitelist(methods=["GET"])
def search_supplier_document_review_options(
	kind: str,
	txt: str = "",
	company: str = "",
) -> list[dict[str, str]]:
	_assert_internal_review_user()
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	if kind == "company":
		rows = frappe.get_list(
			"Company",
			filters={"name": ["like", f"%{txt}%"]},
			fields=["name"],
			order_by="name asc",
			limit_page_length=MAX_LINK_RESULTS,
		)
		return [{"value": row.name, "label": row.name} for row in rows]
	if kind == "branch":
		rows = branch_query("Branch", txt, "name", 0, MAX_LINK_RESULTS, {"company": company})
		return [{"value": row[0], "label": row[0]} for row in rows]
	if kind == "supplier":
		rows = search_link(
			"Supplier",
			txt,
			page_length=MAX_LINK_RESULTS,
			reference_doctype="Purchase Order",
			link_fieldname="supplier",
		)
		return [
			{"value": str(row.get("value") or ""), "label": str(row.get("description") or row.get("value") or "")}
			for row in rows
		]
	frappe.throw(_("Unsupported supplier document review search type."), frappe.ValidationError)
	return []


def _latest_extraction_with_review(intake_name: str) -> tuple[Any | None, Any | None]:
	extractions = frappe.get_list(
		"Supplier Document Extraction",
		filters={"supplier_document_intake": intake_name},
		fields=["name"],
		order_by="extracted_on desc, creation desc",
		limit_page_length=1,
	)
	if not extractions:
		return None, None
	extraction = frappe.get_doc("Supplier Document Extraction", extractions[0].name)
	reviews = frappe.get_list(
		"Supplier Document Extraction Review",
		filters={"extraction": extraction.name},
		fields=["name", "decision"],
		order_by="reviewed_on desc, creation desc",
		limit_page_length=1,
	)
	review = frappe.get_doc("Supplier Document Extraction Review", reviews[0].name) if reviews else None
	return extraction, review


@frappe.whitelist(methods=["POST"])
def review_supplier_document_intake(
	intake_name: str,
	review_status: str,
	review_notes: str = "",
) -> dict[str, Any]:
	_assert_internal_review_user()
	review_status = str(review_status or "").strip().title()
	if review_status not in ALLOWED_INTAKE_REVIEW_STATUSES:
		frappe.throw(_("Choose In Review, Accepted or Rejected."), frappe.ValidationError)
	intake_name = str(intake_name or "").strip()
	frappe.db.sql(
		"select name from `tabSupplier Document Intake` where name=%s for update",
		(intake_name,),
	)
	if not intake_name or not frappe.db.exists("Supplier Document Intake", intake_name):
		frappe.throw(_("Supplier Document Intake was not found."), frappe.DoesNotExistError)
	intake = frappe.get_doc("Supplier Document Intake", intake_name)
	intake.check_permission("read")
	intake.check_permission("write")
	_assert_company_read(intake.company)
	po = frappe.get_doc("Purchase Order", intake.purchase_order)
	po.check_permission("read")
	po_branch_field = _purchase_order_branch_field()
	po_branch = str(po.get(po_branch_field) or "") if po_branch_field else ""
	if po_branch:
		validate_user_branch_access(po_branch, user=frappe.session.user, company=intake.company, throw=True)

	notes = _clean_notes(review_notes, required=review_status == "Rejected")
	if review_status == "Accepted":
		extraction, review = _latest_extraction_with_review(intake.name)
		if not extraction or not review or review.decision != "Accepted":
			frappe.throw(
				_("Accept the latest extraction evidence before accepting the supplier document."),
				frappe.ValidationError,
			)
	intake.review_status = review_status
	intake.review_notes = notes
	intake.save()
	return {
		"intake": intake.name,
		"review_status": intake.review_status,
		"reviewed_by": intake.reviewed_by,
		"reviewed_on": intake.reviewed_on,
		"native_buying_document_created": False,
		"accounting_mutated": False,
	}


def _existing_handoff(extraction_name: str):
	rows = frappe.get_list(
		"Supplier Document Purchase Invoice Handoff",
		filters={"extraction": extraction_name},
		fields=["name", "purchase_invoice"],
		order_by="creation desc",
		limit_page_length=1,
	)
	return rows[0] if rows else None


def _assert_purchase_invoice_create_permission() -> None:
	if not frappe.has_permission("Purchase Invoice", "create"):
		frappe.throw(_("You do not have permission to create Purchase Invoice drafts."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def prepare_draft_purchase_invoice(extraction_name: str) -> dict[str, Any]:
	user = _assert_internal_review_user()
	_assert_purchase_invoice_create_permission()
	extraction_name = str(extraction_name or "").strip()
	frappe.db.sql(
		"select name from `tabSupplier Document Extraction` where name=%s for update",
		(extraction_name,),
	)
	if not extraction_name or not frappe.db.exists("Supplier Document Extraction", extraction_name):
		frappe.throw(_("Supplier Document Extraction was not found."), frappe.DoesNotExistError)

	extraction = frappe.get_doc("Supplier Document Extraction", extraction_name)
	extraction.check_permission("read")
	review_rows = frappe.get_list(
		"Supplier Document Extraction Review",
		filters={"extraction": extraction.name},
		fields=["name", "decision"],
		order_by="reviewed_on desc, creation desc",
		limit_page_length=1,
	)
	if not review_rows or review_rows[0].decision != "Accepted":
		frappe.throw(_("Only accepted extraction evidence can prepare a Purchase Invoice draft."), frappe.ValidationError)
	review = frappe.get_doc("Supplier Document Extraction Review", review_rows[0].name)

	intake = frappe.get_doc("Supplier Document Intake", extraction.supplier_document_intake)
	intake.check_permission("read")
	if intake.review_status != "Accepted":
		frappe.throw(_("Accept the supplier document before preparing a Purchase Invoice draft."), frappe.ValidationError)
	if intake.document_type != "Supplier Invoice":
		frappe.throw(_("Only Supplier Invoice intake records can prepare Purchase Invoice drafts."), frappe.ValidationError)

	po = frappe.get_doc("Purchase Order", intake.purchase_order)
	po.check_permission("read")
	if po.docstatus != 1:
		frappe.throw(_("The authoritative Purchase Order must be submitted."), frappe.ValidationError)
	if po.supplier != intake.supplier or po.company != intake.company:
		frappe.throw(_("Supplier document authority no longer matches its Purchase Order."), frappe.ValidationError)
	if extraction.supplier != intake.supplier or extraction.company != intake.company or extraction.purchase_order != po.name:
		frappe.throw(_("Extraction authority no longer matches its Supplier Document Intake."), frappe.ValidationError)

	_assert_company_read(po.company)
	po_branch_field = _purchase_order_branch_field()
	po_branch = str(po.get(po_branch_field) or "") if po_branch_field else ""
	if po_branch:
		validate_user_branch_access(po_branch, user=user, company=po.company, throw=True)

	existing = _existing_handoff(extraction.name)
	if existing:
		if frappe.db.exists("Purchase Invoice", existing.purchase_invoice):
			docstatus = int(frappe.db.get_value("Purchase Invoice", existing.purchase_invoice, "docstatus") or 0)
			return {
				"handoff": existing.name,
				"purchase_invoice": existing.purchase_invoice,
				"docstatus": docstatus,
				"route": f"/app/purchase-invoice/{existing.purchase_invoice}",
				"created": False,
				"idempotent": True,
			}
		frappe.throw(
			_("This extraction already has an immutable Purchase Invoice handoff whose draft no longer exists. Record a new extraction before preparing another draft."),
			frappe.ValidationError,
		)

	document_number = str(extraction.extracted_document_number or "").strip()
	if not document_number:
		frappe.throw(
			_("The accepted extraction needs a supplier document number before a draft Purchase Invoice can be prepared."),
			frappe.ValidationError,
		)

	purchase_invoice = make_purchase_invoice(po.name)
	if purchase_invoice.doctype != "Purchase Invoice":
		frappe.throw(_("ERPNext did not return a Purchase Invoice draft from the Purchase Order."), frappe.ValidationError)
	if purchase_invoice.supplier != po.supplier or purchase_invoice.company != po.company:
		frappe.throw(_("ERPNext Purchase Invoice mapping returned unexpected Supplier or Company authority."), frappe.ValidationError)
	if not purchase_invoice.get("items"):
		frappe.throw(_("The Purchase Order has no remaining billable items for a new Purchase Invoice."), frappe.ValidationError)

	extracted_currency = str(extraction.extracted_currency or "").strip()
	if extracted_currency and extracted_currency != str(purchase_invoice.currency or ""):
		frappe.throw(
			_("Extracted currency {0} does not match the ERPNext Purchase Order currency {1}. Use the native buying workflow to resolve the discrepancy.").format(
				extracted_currency, purchase_invoice.currency
			),
			frappe.ValidationError,
		)

	purchase_invoice.bill_no = document_number
	if extraction.extracted_document_date:
		purchase_invoice.bill_date = getdate(extraction.extracted_document_date)

	pi_branch_field = _purchase_invoice_branch_field()
	if po_branch and pi_branch_field and not purchase_invoice.get(pi_branch_field):
		purchase_invoice.set(pi_branch_field, po_branch)

	purchase_invoice.insert()
	if purchase_invoice.docstatus != 0:
		frappe.throw(_("Supplier document handoff may create only a draft Purchase Invoice."), frappe.ValidationError)

	extracted_total = flt(extraction.extracted_total) if extraction.extracted_total not in (None, "") else None
	mapped_total = flt(purchase_invoice.grand_total)
	total_difference = mapped_total - extracted_total if extracted_total is not None else None

	handoff = frappe.new_doc("Supplier Document Purchase Invoice Handoff")
	handoff.update(
		{
			"handoff_key": f"SDPIH-{uuid4().hex}",
			"extraction": extraction.name,
			"extraction_review": review.name,
			"supplier_document_intake": intake.name,
			"supplier": intake.supplier,
			"company": intake.company,
			"purchase_order": po.name,
			"purchase_invoice": purchase_invoice.name,
			"source_file": extraction.source_file,
			"created_by": user,
			"created_on": now_datetime(),
			"mapped_grand_total": mapped_total,
			"mapped_currency": purchase_invoice.currency,
			"extracted_total": extracted_total,
			"extracted_currency": extracted_currency,
			"total_difference": total_difference,
		}
	)
	handoff.flags.supplier_document_purchase_invoice_handoff_api_write = True
	handoff.insert(ignore_permissions=True)

	return {
		"handoff": handoff.name,
		"purchase_invoice": purchase_invoice.name,
		"docstatus": purchase_invoice.docstatus,
		"route": f"/app/purchase-invoice/{purchase_invoice.name}",
		"created": True,
		"idempotent": False,
		"mapped_grand_total": mapped_total,
		"mapped_currency": purchase_invoice.currency,
		"extracted_total": extracted_total,
		"total_difference": total_difference,
		"source_of_truth": "ERPNext Purchase Order mapping",
		"extraction_is_advisory": True,
	}
