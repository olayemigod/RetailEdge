from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

from retailedge import supplier_document_review as review
from retailedge.branch_context import validate_user_branch_access
from retailedge.stock_movement_filters import branch_query


PO_BASE_FIELDS = [
	"name",
	"supplier",
	"company",
	"docstatus",
	"status",
	"transaction_date",
	"currency",
	"grand_total",
]


def _controlled_purchase_order_snapshot(intake: Any, *, user: str) -> frappe._dict | None:
	"""Read only the exact PO already authorised by a visible review intake.

	This is intentionally narrower than granting Purchase Order read permission to
	Accounts roles. The projection is accepted only when Supplier and Company still
	match the intake and the user's Branch scope still permits the PO.
	"""
	purchase_order = str(getattr(intake, "purchase_order", "") or "").strip()
	if not purchase_order:
		return None

	branch_field = review._purchase_order_branch_field()
	fields = list(PO_BASE_FIELDS)
	if branch_field:
		fields.append(branch_field)

	row = frappe.db.get_value("Purchase Order", purchase_order, fields, as_dict=True)
	if not row:
		return None
	if str(row.get("company") or "") != str(getattr(intake, "company", "") or ""):
		return None
	if str(row.get("supplier") or "") != str(getattr(intake, "supplier", "") or ""):
		return None

	company = str(row.get("company") or "")
	branch = str(row.get(branch_field) or "") if branch_field else ""
	allowed = review._allowed_branch_names(user=user, company=company)
	if allowed is not None and (not branch or branch not in allowed):
		return None
	if branch:
		validate_user_branch_access(branch, user=user, company=company, throw=True)
	return frappe._dict(row)


@frappe.whitelist(methods=["GET"])
def get_supplier_document_review_context(
	company: str = "",
	branch: str = "",
	supplier: str = "",
	status: str = "Open",
	limit: int = review.MAX_QUEUE_ROWS,
) -> dict[str, Any]:
	user = review._assert_internal_review_user()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(branch or "").strip()
	supplier = str(supplier or "").strip()
	status = str(status or "Open").strip().title()
	limit = max(1, min(cint(limit) or review.MAX_QUEUE_ROWS, review.MAX_QUEUE_ROWS))

	if company:
		review._assert_company_read(company)
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
		return review._review_context_payload(company=company, branch=branch, user=user, rows=[])

	intake_names = [row.name for row in intakes]
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
	latest_extraction = review._latest_by([dict(row) for row in extraction_rows], "supplier_document_intake")
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
		review_by_extraction = review._latest_by([dict(row) for row in review_rows], "extraction")

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
		handoff_by_extraction = review._latest_by([dict(row) for row in handoff_rows], "extraction")

	rows: list[dict[str, Any]] = []
	po_cache: dict[tuple[str, str, str], frappe._dict | None] = {}
	for intake in intakes:
		po_name = str(intake.purchase_order or "")
		po_cache_key = (po_name, str(intake.company or ""), str(intake.supplier or ""))
		if po_cache_key not in po_cache:
			po_cache[po_cache_key] = _controlled_purchase_order_snapshot(intake, user=user)
		po = po_cache[po_cache_key]
		if not po:
			continue
		po_branch_field = review._purchase_order_branch_field()
		po_branch = str(po.get(po_branch_field) or "") if po_branch_field else ""
		if branch and po_branch != branch:
			continue

		extraction = latest_extraction.get(intake.name)
		extraction_review = review_by_extraction.get(extraction["name"]) if extraction else None
		handoff = handoff_by_extraction.get(extraction["name"]) if extraction else None
		extraction_decision = str(extraction_review.get("decision") or "") if extraction_review else "Pending Review"
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
				"source_file_url": review._get_private_file_url(extraction.get("source_file") if extraction else ""),
				"extracted_document_number": extraction.get("extracted_document_number") if extraction else "",
				"extracted_document_date": extraction.get("extracted_document_date") if extraction else None,
				"extracted_currency": extraction.get("extracted_currency") if extraction else "",
				"extracted_subtotal": extraction.get("extracted_subtotal") if extraction else None,
				"extracted_tax_amount": extraction.get("extracted_tax_amount") if extraction else None,
				"extracted_total": extraction.get("extracted_total") if extraction else None,
				"extracted_purchase_order_reference": extraction.get("extracted_purchase_order_reference") if extraction else "",
				"confidence": extraction.get("confidence") if extraction else None,
				"extraction_review_status": extraction_decision,
				"extraction_review": extraction_review.get("name") if extraction_review else "",
				"extraction_review_notes": extraction_review.get("review_notes") if extraction_review else "",
				"handoff": handoff.get("name") if handoff else "",
				"purchase_invoice": handoff.get("purchase_invoice") if handoff else "",
				"mapped_grand_total": handoff.get("mapped_grand_total") if handoff else None,
				"total_difference": handoff.get("total_difference") if handoff else None,
				"ready_for_draft_purchase_invoice": ready,
			}
		)

	return review._review_context_payload(company=company, branch=branch, user=user, rows=rows)


@frappe.whitelist(methods=["GET"])
def search_supplier_document_review_options(
	kind: str,
	txt: str = "",
	company: str = "",
) -> list[dict[str, str]]:
	review._assert_internal_review_user()
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()

	if kind == "company":
		rows = frappe.get_list(
			"Company",
			filters={"name": ["like", f"%{txt}%"]},
			fields=["name"],
			order_by="name asc",
			limit_page_length=review.MAX_LINK_RESULTS,
		)
		return [{"value": row.name, "label": row.name} for row in rows]
	if kind == "branch":
		rows = branch_query("Branch", txt, "name", 0, review.MAX_LINK_RESULTS, {"company": company})
		return [{"value": row[0], "label": row[0]} for row in rows]
	if kind == "supplier":
		rows = search_link("Supplier", txt, page_length=review.MAX_LINK_RESULTS)
		return [
			{"value": str(row.get("value") or ""), "label": str(row.get("description") or row.get("value") or "")}
			for row in rows
		]

	frappe.throw(_("Unsupported supplier document review search type."), frappe.ValidationError)
	return []
