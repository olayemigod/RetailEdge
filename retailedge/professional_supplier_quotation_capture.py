from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate

from erpnext.buying.doctype.request_for_quotation.request_for_quotation import make_supplier_quotation_from_rfq

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	has_field,
	user_has_global_branch_access,
	validate_user_branch_access,
)

REQUEST_FOR_QUOTATION_DOCTYPE = "Request for Quotation"
SUPPLIER_QUOTATION_DOCTYPE = "Supplier Quotation"
SUPPLIER_DOCTYPE = "Supplier"


def _permission(doctype: str, ptype: str, name: str | None = None) -> bool:
	try:
		return bool(frappe.has_permission(doctype, ptype, doc=name))
	except Exception:
		return False


def _transaction_branch_field(doctype: str) -> str | None:
	if has_field(doctype, "retailedge_branch"):
		return "retailedge_branch"
	return get_first_existing_field(doctype, BRANCH_FIELD_CANDIDATES)


def _document_branch(doc: Any) -> str:
	field = _transaction_branch_field(doc.doctype)
	return str(getattr(doc, field, None) or "") if field else ""


def _assert_read(doctype: str, name: str) -> None:
	if not _permission(doctype, "read", name):
		frappe.throw(_("You do not have permission to read {0}.").format(_(doctype)), frappe.PermissionError)


def _assert_standard_permissions() -> None:
	if not _permission(SUPPLIER_QUOTATION_DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Supplier Quotations."), frappe.PermissionError)
	if not _permission(SUPPLIER_QUOTATION_DOCTYPE, "submit"):
		frappe.throw(_("You do not have permission to submit Supplier Quotations."), frappe.PermissionError)


def _active_supplier_quotation_workflow() -> str:
	return str(
		frappe.db.get_value(
			"Workflow",
			{"document_type": SUPPLIER_QUOTATION_DOCTYPE, "is_active": 1},
			"name",
		)
		or ""
	)


def _validate_rfq_scope(doc: Any) -> str:
	if getattr(doc, "docstatus", 0) != 1:
		frappe.throw(_("Only submitted Requests for Quotation can receive a guided Supplier Quotation."))
	company = str(getattr(doc, "company", None) or "").strip()
	if not company:
		frappe.throw(_("The Request for Quotation has no Company."))
	_assert_read("Company", company)

	branch = _document_branch(doc)
	global_access = user_has_global_branch_access(user=frappe.session.user)
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)
	elif not global_access:
		frappe.throw(
			_("Request for Quotation {0} has no Branch attribution for your restricted access.").format(doc.name),
			frappe.PermissionError,
		)
	return branch


def _rfq_supplier_options(doc: Any) -> list[dict[str, str]]:
	options: list[dict[str, str]] = []
	seen: set[str] = set()
	for row in getattr(doc, "suppliers", None) or []:
		supplier = str(getattr(row, "supplier", None) or "").strip()
		if not supplier or supplier in seen:
			continue
		seen.add(supplier)
		label = str(getattr(row, "supplier_name", None) or supplier)
		options.append({"value": supplier, "label": label})
	return options


def _validate_supplier(doc: Any, supplier: str) -> None:
	supplier = str(supplier or "").strip()
	if not supplier:
		frappe.throw(_("Choose the Supplier whose quotation was received."))
	allowed = {option["value"] for option in _rfq_supplier_options(doc)}
	if supplier not in allowed:
		frappe.throw(_("Supplier {0} is not part of Request for Quotation {1}.").format(supplier, doc.name))
	_assert_read(SUPPLIER_DOCTYPE, supplier)


def _existing_supplier_quotation(rfq: str, supplier: str) -> str:
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT sq.name
		FROM `tabSupplier Quotation` sq
		INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
		WHERE sq.docstatus < 2
			AND sq.supplier = %s
			AND sqi.request_for_quotation = %s
		ORDER BY sq.creation DESC
		LIMIT 1
		""",
		(supplier, rfq),
		as_dict=True,
	)
	return str(rows[0].get("name") or "") if rows else ""


def _mapped_supplier_quotation(doc: Any, supplier: str) -> Any:
	mapped = make_supplier_quotation_from_rfq(doc.name, for_supplier=supplier)
	if not mapped or getattr(mapped, "doctype", "") != SUPPLIER_QUOTATION_DOCTYPE:
		frappe.throw(_("ERPNext could not map the Request for Quotation to a Supplier Quotation."))
	branch = _document_branch(doc)
	branch_field = _transaction_branch_field(SUPPLIER_QUOTATION_DOCTYPE)
	if branch and branch_field:
		setattr(mapped, branch_field, branch)
	return mapped


def _standard_blockers(doc: Any, supplier: str) -> list[str]:
	blockers: list[str] = []
	if not _permission(SUPPLIER_QUOTATION_DOCTYPE, "create"):
		blockers.append(_("You do not have permission to create Supplier Quotations."))
	if not _permission(SUPPLIER_QUOTATION_DOCTYPE, "submit"):
		blockers.append(_("You do not have permission to submit Supplier Quotations."))
	workflow = _active_supplier_quotation_workflow()
	if workflow:
		blockers.append(_("Supplier Quotation approval Workflow {0} is active. Use the governed ERPNext workflow.").format(workflow))
	if supplier:
		existing = _existing_supplier_quotation(doc.name, supplier)
		if existing:
			if _permission(SUPPLIER_QUOTATION_DOCTYPE, "read", existing):
				blockers.append(_("Supplier Quotation {0} already exists for this Supplier and RFQ.").format(existing))
			else:
				blockers.append(_("A Supplier Quotation already exists for this Supplier and RFQ."))
	return blockers


def _coerce_item_rates(item_rates: list[Any] | str | None) -> dict[str, float]:
	if isinstance(item_rates, str):
		try:
			item_rates = frappe.parse_json(item_rates)
		except Exception:
			item_rates = []
	if not isinstance(item_rates, (list, tuple)):
		frappe.throw(_("Supplier quotation item rates are invalid."))

	rates: dict[str, float] = {}
	for row in item_rates:
		if not isinstance(row, dict):
			frappe.throw(_("Each supplier quotation rate must identify one RFQ item."))
		key = str(row.get("request_for_quotation_item") or "").strip()
		if not key:
			frappe.throw(_("Each supplier quotation rate must identify one RFQ item."))
		if key in rates:
			frappe.throw(_("RFQ item {0} was supplied more than once.").format(key))
		rate = flt(row.get("rate"))
		if rate < 0:
			frappe.throw(_("Quoted rates cannot be negative."))
		rates[key] = rate
	return rates


def _apply_rates(mapped: Any, item_rates: list[Any] | str | None) -> None:
	rates = _coerce_item_rates(item_rates)
	expected = {
		str(getattr(row, "request_for_quotation_item", None) or "").strip()
		for row in mapped.get("items") or []
	}
	if "" in expected:
		frappe.throw(_("ERPNext returned an RFQ item without a source-row reference."))
	if set(rates) != expected:
		frappe.throw(_("Enter one quoted rate for every RFQ item and do not add unrelated items."))
	for row in mapped.get("items") or []:
		row.rate = rates[str(row.request_for_quotation_item)]


@frappe.whitelist()
def get_supplier_quotation_capture_preview(
	request_for_quotation: str,
	supplier: str | None = None,
) -> dict[str, Any]:
	request_for_quotation = str(request_for_quotation or "").strip()
	if not request_for_quotation:
		frappe.throw(_("Request for Quotation is required."))
	_assert_read(REQUEST_FOR_QUOTATION_DOCTYPE, request_for_quotation)
	rfq = frappe.get_doc(REQUEST_FOR_QUOTATION_DOCTYPE, request_for_quotation)
	branch = _validate_rfq_scope(rfq)
	selected_supplier = str(supplier or "").strip()
	if selected_supplier:
		_validate_supplier(rfq, selected_supplier)

	blockers = _standard_blockers(rfq, selected_supplier)
	items: list[dict[str, Any]] = []
	currency = ""
	if selected_supplier and not blockers:
		mapped = _mapped_supplier_quotation(rfq, selected_supplier)
		if getattr(mapped, "is_subcontracted", 0):
			blockers.append(_("Subcontracted Supplier Quotations remain an Advanced ERPNext workflow."))
		else:
			currency = str(getattr(mapped, "currency", None) or "")
			items = [
				{
					"request_for_quotation_item": str(getattr(row, "request_for_quotation_item", None) or ""),
					"item_code": getattr(row, "item_code", None),
					"item_name": getattr(row, "item_name", None),
					"description": getattr(row, "description", None),
					"qty": flt(getattr(row, "qty", 0)),
					"uom": getattr(row, "uom", None),
					"rate": flt(getattr(row, "rate", 0)),
				}
				for row in mapped.get("items") or []
			]

	return {
		"request_for_quotation": rfq.name,
		"expected_rfq_modified": cstr(rfq.modified),
		"company": rfq.company,
		"branch": branch,
		"supplier": selected_supplier,
		"suppliers": _rfq_supplier_options(rfq),
		"currency": currency,
		"transaction_date": nowdate(),
		"items": items,
		"blockers": blockers,
		"can_record": bool(selected_supplier and items and not blockers),
		"persistence": "none",
		"source_of_truth": "ERPNext RFQ to Supplier Quotation mapper",
	}


@frappe.whitelist(methods=["POST"])
def record_submitted_supplier_quotation_from_rfq(
	request_for_quotation: str,
	supplier: str,
	expected_rfq_modified: str,
	item_rates: list[Any] | str,
	transaction_date: str | None = None,
	valid_till: str | None = None,
	quotation_number: str | None = None,
) -> dict[str, Any]:
	request_for_quotation = str(request_for_quotation or "").strip()
	supplier = str(supplier or "").strip()
	if not request_for_quotation or not supplier:
		frappe.throw(_("Request for Quotation and Supplier are required."))
	_assert_read(REQUEST_FOR_QUOTATION_DOCTYPE, request_for_quotation)
	_assert_standard_permissions()

	locked = frappe.db.sql(
		"SELECT modified, docstatus FROM `tabRequest for Quotation` WHERE name = %s FOR UPDATE",
		(request_for_quotation,),
		as_dict=True,
	)
	if not locked:
		frappe.throw(_("Request for Quotation {0} no longer exists.").format(request_for_quotation))
	if cstr(locked[0].get("modified")) != cstr(expected_rfq_modified):
		frappe.throw(_("The Request for Quotation changed after your review. Refresh before recording the supplier response."))

	rfq = frappe.get_doc(REQUEST_FOR_QUOTATION_DOCTYPE, request_for_quotation)
	_validate_rfq_scope(rfq)
	_validate_supplier(rfq, supplier)
	blockers = _standard_blockers(rfq, supplier)
	if blockers:
		frappe.throw("\n".join(str(message) for message in blockers))

	mapped = _mapped_supplier_quotation(rfq, supplier)
	if getattr(mapped, "is_subcontracted", 0):
		frappe.throw(_("Subcontracted Supplier Quotations remain an Advanced ERPNext workflow."))
	_apply_rates(mapped, item_rates)
	mapped.transaction_date = transaction_date or nowdate()
	if valid_till:
		if getdate(valid_till) < getdate(mapped.transaction_date):
			frappe.throw(_("Valid Till cannot be before the quotation date."))
		mapped.valid_till = valid_till
	mapped.quotation_number = str(quotation_number or "").strip() or None

	mapped.insert()
	mapped.submit()
	return {
		"name": mapped.name,
		"docstatus": getattr(mapped, "docstatus", 0),
		"status": getattr(mapped, "status", "Submitted"),
		"supplier": mapped.supplier,
		"currency": mapped.currency,
		"grand_total": flt(mapped.grand_total),
		"request_for_quotation": request_for_quotation,
		"source_of_truth": "ERPNext Supplier Quotation insert + submit",
	}
