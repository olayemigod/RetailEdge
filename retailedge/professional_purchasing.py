from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt, getdate, nowdate
from frappe.utils.user import get_user_fullname

from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
from erpnext.stock.doctype.material_request.material_request import make_request_for_quotation

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	get_user_allowed_branches,
	has_field,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.operating_context import get_operating_context

PURCHASE_ORDER_DOCTYPE = "Purchase Order"
PURCHASE_RECEIPT_DOCTYPE = "Purchase Receipt"
MATERIAL_REQUEST_DOCTYPE = "Material Request"
REQUEST_FOR_QUOTATION_DOCTYPE = "Request for Quotation"
SUPPLIER_QUOTATION_DOCTYPE = "Supplier Quotation"
SUPPLIER_DOCTYPE = "Supplier"
SUPPLIER_QUOTATION_COMPARISON_REPORT = "Supplier Quotation Comparison"
PURCHASE_ORDER_ANALYSIS_REPORT = "Purchase Order Analysis"
MAX_PURCHASE_ORDERS = 200
MAX_MATERIAL_REQUESTS = 200
MAX_RFQ_SUPPLIERS = 20
MAX_LINK_RESULTS = 20
ATTENTION_TOLERANCE = 0.01
CLOSED_PURCHASE_ORDER_STATUSES = {"Closed", "Completed", "Cancelled", "Stopped", "On Hold"}


def _permission(doctype: str, ptype: str, name: str | None = None) -> bool:
	try:
		return bool(frappe.has_permission(doctype, ptype, doc=name))
	except Exception:
		return False


def _assert_read(doctype: str, name: str | None = None) -> None:
	if not _permission(doctype, "read", name):
		frappe.throw(_("You do not have permission to read {0}.").format(_(doctype)), frappe.PermissionError)


def _assert_create(doctype: str) -> None:
	if not _permission(doctype, "create"):
		frappe.throw(_("You do not have permission to create {0}.").format(_(doctype)), frappe.PermissionError)


def _transaction_branch_field(doctype: str) -> str | None:
	if has_field(doctype, "retailedge_branch"):
		return "retailedge_branch"
	return get_first_existing_field(doctype, BRANCH_FIELD_CANDIDATES)


def _document_branch(doc: Any) -> str:
	field = _transaction_branch_field(doc.doctype)
	return str(getattr(doc, field, None) or "") if field else ""


def _resolve_scope(company: str | None = None, branch: str | None = None) -> tuple[str, str, list[str], bool]:
	operating = get_operating_context() or {}
	resolved_company = str(
		company
		or operating.get("company")
		or frappe.defaults.get_user_default("Company")
		or ""
	).strip()
	if not resolved_company:
		frappe.throw(_("Choose an Operating Company before using Professional Purchasing."))
	_assert_read("Company", resolved_company)

	resolved_branch = str(branch or "").strip()
	if not resolved_branch and (not company or resolved_company == str(operating.get("company") or "")):
		resolved_branch = str(operating.get("branch") or "").strip()
	if resolved_branch:
		validate_user_branch_access(
			resolved_branch,
			user=frappe.session.user,
			company=resolved_company,
			throw=True,
		)

	global_access = user_has_global_branch_access(user=frappe.session.user)
	allowed = list(
		get_user_allowed_branches(user=frappe.session.user, company=resolved_company).get("branches") or []
	)
	if resolved_branch and allowed and not global_access and resolved_branch not in allowed:
		frappe.throw(_("You do not have access to Branch {0}.").format(resolved_branch), frappe.PermissionError)
	return resolved_company, resolved_branch, allowed, global_access


def _branch_scoped_filters(
	doctype: str,
	*,
	company: str,
	branch: str,
	allowed_branches: list[str],
	global_branch_access: bool,
) -> tuple[dict[str, Any], str | None]:
	filters: dict[str, Any] = {"company": company}
	branch_field = _transaction_branch_field(doctype)
	if branch:
		if not branch_field:
			frappe.throw(
				_("{0} branch attribution is unavailable. Run site migration before using a Branch-scoped purchasing workspace.").format(doctype)
			)
		filters[branch_field] = branch
	elif not global_branch_access:
		if not branch_field:
			frappe.throw(
				_("{0} branch attribution is unavailable. Run site migration before using restricted Branch purchasing access.").format(doctype)
			)
		filters[branch_field] = ["in", allowed_branches or ["__no_permitted_branch__"]]
	return filters, branch_field


def _purchase_order_filters(
	*,
	company: str,
	branch: str,
	supplier: str,
	allowed_branches: list[str],
	global_branch_access: bool,
) -> tuple[dict[str, Any], str | None]:
	filters, branch_field = _branch_scoped_filters(
		PURCHASE_ORDER_DOCTYPE,
		company=company,
		branch=branch,
		allowed_branches=allowed_branches,
		global_branch_access=global_branch_access,
	)
	filters["docstatus"] = ["<", 2]
	if supplier:
		filters["supplier"] = supplier
	return filters, branch_field


def _material_request_filters(
	*,
	company: str,
	branch: str,
	allowed_branches: list[str],
	global_branch_access: bool,
) -> tuple[dict[str, Any], str | None]:
	filters, branch_field = _branch_scoped_filters(
		MATERIAL_REQUEST_DOCTYPE,
		company=company,
		branch=branch,
		allowed_branches=allowed_branches,
		global_branch_access=global_branch_access,
	)
	filters.update(
		{
			"docstatus": 1,
			"material_request_type": "Purchase",
			"per_ordered": ["<", 100],
			"status": ["not in", ["Stopped", "Cancelled", "Ordered"]],
		}
	)
	return filters, branch_field


def _get_material_request_rows(
	*,
	company: str,
	branch: str,
	allowed_branches: list[str],
	global_branch_access: bool,
	limit: int,
) -> list[dict[str, Any]]:
	if not _permission(MATERIAL_REQUEST_DOCTYPE, "read"):
		return []
	filters, branch_field = _material_request_filters(
		company=company,
		branch=branch,
		allowed_branches=allowed_branches,
		global_branch_access=global_branch_access,
	)
	fields = [
		"name",
		"docstatus",
		"transaction_date",
		"schedule_date",
		"company",
		"title",
		"status",
		"material_request_type",
		"per_ordered",
		"modified",
	]
	if branch_field:
		fields.append(branch_field)
	rows = frappe.get_list(
		MATERIAL_REQUEST_DOCTYPE,
		filters=filters,
		fields=fields,
		order_by="transaction_date desc, name desc",
		limit_page_length=limit,
	)
	can_create_rfq = _permission(REQUEST_FOR_QUOTATION_DOCTYPE, "create")
	return [
		{
			"name": row.get("name"),
			"docstatus": cint(row.get("docstatus")),
			"transaction_date": row.get("transaction_date"),
			"schedule_date": row.get("schedule_date"),
			"company": row.get("company"),
			"title": row.get("title") or row.get("name"),
			"status": row.get("status") or "Submitted",
			"material_request_type": row.get("material_request_type"),
			"per_ordered": flt(row.get("per_ordered")),
			"branch": str(row.get(branch_field) or "") if branch_field else "",
			"can_start_rfq": bool(can_create_rfq and cint(row.get("docstatus")) == 1 and flt(row.get("per_ordered")) < 100),
			"route": f"/app/material-request/{row.get('name')}",
		}
		for row in rows
	]


def _coerce_supplier_names(suppliers: list[Any] | str | None) -> list[str]:
	if isinstance(suppliers, str):
		try:
			suppliers = frappe.parse_json(suppliers)
		except Exception:
			suppliers = [suppliers]
	if not isinstance(suppliers, (list, tuple)):
		suppliers = []

	names: list[str] = []
	for value in suppliers:
		if isinstance(value, dict):
			value = value.get("value") or value.get("name") or value.get("supplier")
		name = str(value or "").strip()
		if not name:
			continue
		if name in names:
			frappe.throw(_("Supplier {0} was selected more than once.").format(name))
		names.append(name)

	if not names:
		frappe.throw(_("Select at least one Supplier before preparing a Request for Quotation."))
	if len(names) > MAX_RFQ_SUPPLIERS:
		frappe.throw(_("A single guided RFQ can include at most {0} Suppliers.").format(MAX_RFQ_SUPPLIERS))
	return names


def _can_open_report(report_name: str) -> bool:
	try:
		return bool(
			frappe.db.exists("Report", report_name)
			and frappe.has_permission("Report", "read", doc=report_name)
		)
	except Exception:
		return False


def _can_open_supplier_quotation_comparison() -> bool:
	return _can_open_report(SUPPLIER_QUOTATION_COMPARISON_REPORT)


def _classify_purchase_order_attention(row: dict[str, Any], *, today: str | None = None) -> dict[str, Any]:
	"""Classify PO readiness from authoritative ERPNext header progress only.

	This is operational guidance, not a persisted matching or accounting state.
	"""
	docstatus = cint(row.get("docstatus"))
	status = str(row.get("status") or "")
	if docstatus != 1 or status in CLOSED_PURCHASE_ORDER_STATUSES:
		return {"attention_flags": [], "attention_level": "Clear"}

	per_received = flt(row.get("per_received"))
	per_billed = flt(row.get("per_billed"))
	required_date = row.get("schedule_date")
	today_date = getdate(today or nowdate())
	is_overdue = bool(required_date and getdate(required_date) < today_date and per_received < 100 - ATTENTION_TOLERANCE)
	flags: list[dict[str, str]] = []

	if is_overdue:
		flags.append({"key": "overdue_receipt", "label": _("Overdue Receipt"), "kind": "exception"})
	elif per_received < 100 - ATTENTION_TOLERANCE:
		flags.append({"key": "ready_to_receive", "label": _("Ready to Receive"), "kind": "readiness"})

	if per_received > per_billed + ATTENTION_TOLERANCE:
		flags.append({"key": "received_not_billed", "label": _("Received Not Fully Billed"), "kind": "exception"})
	if per_billed > per_received + ATTENTION_TOLERANCE:
		flags.append({"key": "billed_ahead_of_receipt", "label": _("Billed Ahead of Receipt"), "kind": "review"})

	if any(flag["kind"] in {"exception", "review"} for flag in flags):
		level = "Review"
	elif flags:
		level = "Readiness"
	else:
		level = "Clear"
	return {"attention_flags": flags, "attention_level": level}


def _attention_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
	counts = {
		"overdue_receipt": 0,
		"received_not_billed": 0,
		"billed_ahead_of_receipt": 0,
		"ready_to_receive": 0,
		"attention_total": 0,
	}
	for row in rows:
		keys = {flag.get("key") for flag in row.get("attention_flags") or []}
		for key in tuple(counts):
			if key != "attention_total" and key in keys:
				counts[key] += 1
		if any(key in keys for key in {"overdue_receipt", "received_not_billed", "billed_ahead_of_receipt"}):
			counts["attention_total"] += 1
	return counts


@frappe.whitelist()
def get_professional_purchasing_context(
	company: str | None = None,
	branch: str | None = None,
	supplier: str | None = None,
	limit: int | str = 100,
) -> dict[str, Any]:
	"""Return permission-aware sourcing, PO, receipt and attention context from ERPNext."""
	_assert_read(PURCHASE_ORDER_DOCTYPE)
	company, branch, allowed_branches, global_branch_access = _resolve_scope(company, branch)
	supplier = str(supplier or "").strip()
	if supplier:
		_assert_read(SUPPLIER_DOCTYPE, supplier)

	filters, branch_field = _purchase_order_filters(
		company=company,
		branch=branch,
		supplier=supplier,
		allowed_branches=allowed_branches,
		global_branch_access=global_branch_access,
	)
	row_limit = max(1, min(cint(limit) or 100, MAX_PURCHASE_ORDERS))
	fields = [
		"name",
		"docstatus",
		"transaction_date",
		"schedule_date",
		"company",
		"supplier",
		"supplier_name",
		"status",
		"currency",
		"grand_total",
		"per_received",
		"per_billed",
		"is_subcontracted",
		"modified",
	]
	if branch_field:
		fields.append(branch_field)

	rows = frappe.get_list(
		PURCHASE_ORDER_DOCTYPE,
		filters=filters,
		fields=fields,
		order_by="transaction_date desc, name desc",
		limit_page_length=row_limit,
	)
	can_create_receipt = _permission(PURCHASE_RECEIPT_DOCTYPE, "create")
	server_today = nowdate()
	result_rows = []
	for row in rows:
		row_branch = str(row.get(branch_field) or "") if branch_field else ""
		per_received = flt(row.get("per_received"))
		per_billed = flt(row.get("per_billed"))
		status = str(row.get("status") or "")
		can_prepare_receipt = bool(
			can_create_receipt
			and cint(row.get("docstatus")) == 1
			and per_received < 100
			and not cint(row.get("is_subcontracted"))
			and status not in {"Closed", "Completed", "Cancelled"}
		)
		result = {
			"name": row.get("name"),
			"docstatus": cint(row.get("docstatus")),
			"transaction_date": row.get("transaction_date"),
			"schedule_date": row.get("schedule_date"),
			"company": row.get("company"),
			"supplier": row.get("supplier"),
			"supplier_name": row.get("supplier_name") or row.get("supplier"),
			"status": status,
			"currency": row.get("currency"),
			"grand_total": flt(row.get("grand_total")),
			"per_received": per_received,
			"per_billed": per_billed,
			"branch": row_branch,
			"is_subcontracted": bool(cint(row.get("is_subcontracted"))),
			"can_prepare_receipt": can_prepare_receipt,
			"route": f"/app/purchase-order/{row.get('name')}",
		}
		result.update(_classify_purchase_order_attention(result, today=server_today))
		result_rows.append(result)

	material_request_rows = _get_material_request_rows(
		company=company,
		branch=branch,
		allowed_branches=allowed_branches,
		global_branch_access=global_branch_access,
		limit=min(row_limit, MAX_MATERIAL_REQUESTS),
	)
	to_receive = [row for row in result_rows if row["can_prepare_receipt"]]
	attention = _attention_summary(result_rows)
	return {
		"company": company,
		"branch": branch,
		"supplier": supplier,
		"rows": result_rows,
		"material_requests": material_request_rows,
		"summary": {
			"purchase_orders": len(result_rows),
			"to_receive": len(to_receive),
			"drafts": sum(1 for row in result_rows if row["docstatus"] == 0),
			"open_value": sum(row["grand_total"] for row in result_rows if row["docstatus"] == 1),
			"purchase_requests": len(material_request_rows),
			"ready_for_rfq": sum(1 for row in material_request_rows if row["can_start_rfq"]),
			**attention,
		},
		"capabilities": {
			"can_read_purchase_order": True,
			"can_create_purchase_order": _permission(PURCHASE_ORDER_DOCTYPE, "create"),
			"can_read_purchase_receipt": _permission(PURCHASE_RECEIPT_DOCTYPE, "read"),
			"can_create_purchase_receipt": can_create_receipt,
			"can_read_material_request": _permission(MATERIAL_REQUEST_DOCTYPE, "read"),
			"can_read_request_for_quotation": _permission(REQUEST_FOR_QUOTATION_DOCTYPE, "read"),
			"can_create_request_for_quotation": _permission(REQUEST_FOR_QUOTATION_DOCTYPE, "create"),
			"can_read_supplier_quotation": _permission(SUPPLIER_QUOTATION_DOCTYPE, "read"),
			"can_compare_supplier_quotations": _can_open_supplier_quotation_comparison(),
			"can_open_purchase_order_analysis": _can_open_report(PURCHASE_ORDER_ANALYSIS_REPORT),
		},
		"limits": {
			"purchase_orders": MAX_PURCHASE_ORDERS,
			"material_requests": MAX_MATERIAL_REQUESTS,
			"rfq_suppliers": MAX_RFQ_SUPPLIERS,
			"link_results": MAX_LINK_RESULTS,
		},
		"server_today": server_today,
		"source_of_truth": PURCHASE_ORDER_DOCTYPE,
		"sourcing_source_of_truth": "ERPNext Material Request make_request_for_quotation mapper",
		"receipt_source_of_truth": "ERPNext Purchase Order make_purchase_receipt mapper",
		"attention_source_of_truth": "ERPNext Purchase Order schedule_date, status, per_received and per_billed",
		"user_name": get_user_fullname(frappe.session.user),
	}


@frappe.whitelist()
def search_professional_purchasing_options(
	kind: str,
	txt: str = "",
	company: str | None = None,
) -> list[dict[str, Any]]:
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	if kind == "company":
		return search_link("Company", txt, page_length=MAX_LINK_RESULTS)
	if kind in {"supplier", "rfq_supplier"}:
		return search_link(
			SUPPLIER_DOCTYPE,
			txt,
			filters={"disabled": 0},
			page_length=MAX_LINK_RESULTS,
			reference_doctype=REQUEST_FOR_QUOTATION_DOCTYPE if kind == "rfq_supplier" else PURCHASE_ORDER_DOCTYPE,
			link_fieldname="supplier",
		)
	if kind == "branch":
		resolved_company, _branch, allowed, global_access = _resolve_scope(company=company, branch=None)
		filters: dict[str, Any] = {}
		if has_field("Branch", "company"):
			filters["company"] = resolved_company
		if not global_access:
			filters["name"] = ["in", allowed or ["__no_permitted_branch__"]]
		rows = frappe.get_list(
			"Branch",
			filters=filters,
			or_filters={"name": ["like", f"%{txt}%"]} if txt else None,
			fields=["name"],
			order_by="name asc",
			limit_page_length=MAX_LINK_RESULTS,
		)
		return [{"value": row.name, "label": row.name} for row in rows]
	frappe.throw(_("Unsupported Professional Purchasing search type."))
	return []


@frappe.whitelist(methods=["POST"])
def prepare_request_for_quotation_draft(
	material_request: str,
	suppliers: list[Any] | str | None = None,
) -> dict[str, Any]:
	"""Prepare one ERPNext RFQ draft from a submitted Purchase Material Request."""
	material_request = str(material_request or "").strip()
	if not material_request:
		frappe.throw(_("Material Request is required."))
	_assert_read(MATERIAL_REQUEST_DOCTYPE, material_request)
	_assert_create(REQUEST_FOR_QUOTATION_DOCTYPE)
	supplier_names = _coerce_supplier_names(suppliers)
	for supplier in supplier_names:
		_assert_read(SUPPLIER_DOCTYPE, supplier)

	request = frappe.get_doc(MATERIAL_REQUEST_DOCTYPE, material_request)
	if cint(request.docstatus) != 1:
		frappe.throw(_("Only submitted Material Requests can prepare a Request for Quotation."))
	if str(getattr(request, "material_request_type", "") or "") != "Purchase":
		frappe.throw(_("Only Purchase Material Requests can prepare a Request for Quotation."))
	if str(getattr(request, "status", "") or "") in {"Stopped", "Cancelled", "Ordered"}:
		frappe.throw(_("Material Request {0} is not open for sourcing.").format(material_request))
	if flt(getattr(request, "per_ordered", 0)) >= 100:
		frappe.throw(_("Material Request {0} is already fully ordered.").format(material_request))

	branch = _document_branch(request)
	if branch:
		validate_user_branch_access(
			branch,
			user=frappe.session.user,
			company=request.company,
			throw=True,
		)

	rfq = make_request_for_quotation(request.name)
	if not rfq or getattr(rfq, "doctype", None) != REQUEST_FOR_QUOTATION_DOCTYPE:
		frappe.throw(_("ERPNext could not prepare a Request for Quotation from {0}.").format(material_request))
	if str(getattr(rfq, "company", "") or "") != str(request.company or ""):
		frappe.throw(_("Mapped Request for Quotation Company does not match the Material Request."))

	items = [row for row in (getattr(rfq, "items", None) or []) if flt(getattr(row, "qty", 0)) > 0]
	if not items:
		frappe.throw(_("Material Request {0} has no remaining quantities available for RFQ.").format(material_request))
	if any(str(getattr(row, "material_request", "") or "") != request.name for row in items):
		frappe.throw(_("Mapped Request for Quotation contains items outside Material Request {0}.").format(material_request))

	rfq_branch_field = _transaction_branch_field(REQUEST_FOR_QUOTATION_DOCTYPE)
	if branch and rfq_branch_field:
		setattr(rfq, rfq_branch_field, branch)
	elif branch and not rfq_branch_field:
		frappe.throw(
			_("Request for Quotation branch attribution is unavailable. Run site migration before using this Branch-scoped action.")
		)

	for supplier in supplier_names:
		rfq.append("suppliers", {"supplier": supplier, "send_email": 0})

	# ERPNext RFQ validation remains authoritative for Supplier eligibility,
	# scorecard controls, item references and mandatory document fields.
	rfq.insert()
	if cint(rfq.docstatus) != 0:
		frappe.throw(_("Guided sourcing may prepare only a draft Request for Quotation."))
	return {
		"doctype": rfq.doctype,
		"name": rfq.name,
		"docstatus": cint(rfq.docstatus),
		"material_request": request.name,
		"company": rfq.company,
		"branch": getattr(rfq, rfq_branch_field, "") if rfq_branch_field else "",
		"item_count": len(items),
		"supplier_count": len(supplier_names),
		"suppliers": supplier_names,
		"email_sending": False,
		"posting_status": "Draft",
		"source_of_truth": "ERPNext Material Request make_request_for_quotation mapper",
		"route": f"/app/request-for-quotation/{rfq.name}",
	}


@frappe.whitelist(methods=["POST"])
def prepare_purchase_receipt_draft(purchase_order: str) -> dict[str, Any]:
	"""Prepare one standard ERPNext Purchase Receipt draft from a submitted PO."""
	purchase_order = str(purchase_order or "").strip()
	if not purchase_order:
		frappe.throw(_("Purchase Order is required."))
	_assert_read(PURCHASE_ORDER_DOCTYPE, purchase_order)
	_assert_create(PURCHASE_RECEIPT_DOCTYPE)

	po = frappe.get_doc(PURCHASE_ORDER_DOCTYPE, purchase_order)
	if cint(po.docstatus) != 1:
		frappe.throw(_("Only submitted Purchase Orders can prepare a Purchase Receipt."))
	if str(getattr(po, "status", "") or "") in {"Closed", "Completed", "Cancelled"}:
		frappe.throw(_("Purchase Order {0} is not open for receiving.").format(purchase_order))
	if flt(getattr(po, "per_received", 0)) >= 100:
		frappe.throw(_("Purchase Order {0} is already fully received.").format(purchase_order))
	if cint(getattr(po, "is_subcontracted", 0)):
		frappe.throw(_("Use the full ERPNext Purchase Order workflow for subcontracted orders."))

	branch = _document_branch(po)
	if branch:
		validate_user_branch_access(
			branch,
			user=frappe.session.user,
			company=po.company,
			throw=True,
		)

	receipt = make_purchase_receipt(po.name)
	if not receipt or getattr(receipt, "doctype", None) != PURCHASE_RECEIPT_DOCTYPE:
		frappe.throw(_("ERPNext could not prepare a Purchase Receipt from {0}.").format(purchase_order))
	items = [row for row in (getattr(receipt, "items", None) or []) if flt(getattr(row, "qty", 0)) > 0]
	if not items:
		frappe.throw(_("Purchase Order {0} has no remaining receivable items.").format(purchase_order))
	if str(getattr(receipt, "company", "") or "") != str(po.company or ""):
		frappe.throw(_("Mapped Purchase Receipt Company does not match the Purchase Order."))
	if str(getattr(receipt, "supplier", "") or "") != str(po.supplier or ""):
		frappe.throw(_("Mapped Purchase Receipt Supplier does not match the Purchase Order."))

	receipt_branch_field = _transaction_branch_field(PURCHASE_RECEIPT_DOCTYPE)
	if branch and receipt_branch_field:
		setattr(receipt, receipt_branch_field, branch)
	elif branch and not receipt_branch_field:
		frappe.throw(
			_("Purchase Receipt branch attribution is unavailable. Run site migration before using this Branch-scoped action.")
		)

	# Insert as the current user. ERPNext Purchase Receipt validation owns stock,
	# quantities, taxes, warehouses and accounting safety. This action stays draft-first.
	receipt.insert()
	return {
		"doctype": receipt.doctype,
		"name": receipt.name,
		"docstatus": cint(receipt.docstatus),
		"purchase_order": po.name,
		"company": receipt.company,
		"supplier": receipt.supplier,
		"branch": getattr(receipt, receipt_branch_field, "") if receipt_branch_field else "",
		"item_count": len(items),
		"posting_status": "Draft",
		"source_of_truth": "ERPNext Purchase Order make_purchase_receipt mapper",
		"route": f"/app/purchase-receipt/{receipt.name}",
	}
