from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.stock.doctype.material_request.material_request import make_request_for_quotation

from retailedge.branch_context import validate_user_branch_access
from retailedge.professional_purchasing import (
	MATERIAL_REQUEST_DOCTYPE,
	REQUEST_FOR_QUOTATION_DOCTYPE,
	SUPPLIER_DOCTYPE,
	_assert_create,
	_assert_read,
	_coerce_supplier_names,
	_document_branch,
	_resolve_scope,
	_transaction_branch_field,
)

CLOSED_MATERIAL_REQUEST_STATUSES = {"Stopped", "Cancelled", "Ordered"}


def _get_open_purchase_request(material_request: str) -> Any:
	material_request = str(material_request or "").strip()
	if not material_request:
		frappe.throw(_("Material Request is required."))
	if not frappe.db.exists(MATERIAL_REQUEST_DOCTYPE, material_request):
		frappe.throw(_("Material Request {0} does not exist.").format(material_request))
	_assert_read(MATERIAL_REQUEST_DOCTYPE, material_request)
	request = frappe.get_doc(MATERIAL_REQUEST_DOCTYPE, material_request)
	if cint(request.docstatus) != 1:
		frappe.throw(_("Only submitted Material Requests can be sourced."))
	if str(getattr(request, "material_request_type", "") or "") != "Purchase":
		frappe.throw(_("Only Purchase Material Requests can prepare a Request for Quotation."))
	if str(getattr(request, "status", "") or "") in CLOSED_MATERIAL_REQUEST_STATUSES:
		frappe.throw(_("Material Request {0} is not open for sourcing.").format(material_request))
	if flt(getattr(request, "per_ordered", 0)) >= 100:
		frappe.throw(_("Material Request {0} is already fully ordered.").format(material_request))
	return request


def _validate_request_scope(request: Any) -> str:
	branch = _document_branch(request)
	_company, _requested_branch, allowed_branches, global_access = _resolve_scope(
		company=str(request.company or ""),
		branch=branch or None,
	)
	if branch:
		validate_user_branch_access(
			branch,
			user=frappe.session.user,
			company=request.company,
			throw=True,
		)
	elif not global_access:
		frappe.throw(
			_("Material Request {0} has no Branch attribution for your restricted access. Ask an authorised manager to correct the document before sourcing it.").format(request.name),
			frappe.PermissionError,
		)
	if branch and allowed_branches and not global_access and branch not in allowed_branches:
		frappe.throw(_("You do not have access to Branch {0}.").format(branch), frappe.PermissionError)
	return branch


def _mapped_rfq_preview(request: Any, branch: str) -> tuple[Any, list[dict[str, Any]]]:
	rfq = make_request_for_quotation(request.name)
	if not rfq or getattr(rfq, "doctype", None) != REQUEST_FOR_QUOTATION_DOCTYPE:
		frappe.throw(_("ERPNext could not preview a Request for Quotation from {0}.").format(request.name))
	if str(getattr(rfq, "company", "") or "") != str(request.company or ""):
		frappe.throw(_("Mapped Request for Quotation Company does not match the Material Request."))

	rfq_branch_field = _transaction_branch_field(REQUEST_FOR_QUOTATION_DOCTYPE)
	if branch and rfq_branch_field:
		setattr(rfq, rfq_branch_field, branch)
	elif branch and not rfq_branch_field:
		frappe.throw(
			_("Request for Quotation branch attribution is unavailable. Run site migration before using this Branch-scoped action.")
		)

	items: list[dict[str, Any]] = []
	for row in getattr(rfq, "items", None) or []:
		if flt(getattr(row, "qty", 0)) <= 0:
			continue
		if str(getattr(row, "material_request", "") or "") != request.name:
			frappe.throw(_("Mapped Request for Quotation contains an item outside Material Request {0}.").format(request.name))
		items.append(
			{
				"item_code": str(getattr(row, "item_code", None) or ""),
				"item_name": str(getattr(row, "item_name", None) or getattr(row, "item_code", None) or ""),
				"qty": flt(getattr(row, "qty", 0)),
				"uom": str(getattr(row, "uom", None) or getattr(row, "stock_uom", None) or ""),
				"schedule_date": str(getattr(row, "schedule_date", None) or ""),
				"warehouse": str(getattr(row, "warehouse", None) or ""),
				"material_request_item": str(getattr(row, "material_request_item", None) or ""),
			}
		)
	if not items:
		frappe.throw(_("Material Request {0} has no remaining quantities available for RFQ.").format(request.name))
	return rfq, items


@frappe.whitelist()
def get_request_for_quotation_preview(
	material_request: str,
	suppliers: list[Any] | str | None = None,
) -> dict[str, Any]:
	"""Preview ERPNext's Purchase Material Request -> RFQ mapping without saving anything."""
	request = _get_open_purchase_request(material_request)
	_assert_create(REQUEST_FOR_QUOTATION_DOCTYPE)
	supplier_names = _coerce_supplier_names(suppliers)
	for supplier in supplier_names:
		_assert_read(SUPPLIER_DOCTYPE, supplier)

	branch = _validate_request_scope(request)
	rfq, items = _mapped_rfq_preview(request, branch)

	return {
		"material_request": request.name,
		"material_request_modified": str(getattr(request, "modified", None) or ""),
		"company": str(request.company or ""),
		"branch": branch,
		"transaction_date": str(getattr(request, "transaction_date", None) or ""),
		"schedule_date": str(getattr(request, "schedule_date", None) or ""),
		"items": items,
		"suppliers": supplier_names,
		"supplier_count": len(supplier_names),
		"item_count": len(items),
		"email_sending": False,
		"persistence": "none",
		"status": "Preview only",
		"source_of_truth": "ERPNext Material Request make_request_for_quotation mapper",
		"next_phase": "RIR2F2E2 standard RFQ review/submit",
		"mapped_doctype": str(getattr(rfq, "doctype", None) or ""),
	}
