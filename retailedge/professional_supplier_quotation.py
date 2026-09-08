from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.professional_purchasing import (
	REQUEST_FOR_QUOTATION_DOCTYPE,
	SUPPLIER_DOCTYPE,
	SUPPLIER_QUOTATION_DOCTYPE,
	_assert_read,
	_branch_scoped_filters,
	_resolve_scope,
	_transaction_branch_field,
)

SUPPLIER_QUOTATION_ITEM_DOCTYPE = "Supplier Quotation Item"
MAX_SUPPLIER_QUOTATION_HISTORY = 100
MAX_REFERENCE_SCAN = 1000


def _docstatus_label(value: int) -> str:
	return {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(cint(value), "Unknown")


def _permitted_rfq_names(
	*,
	company: str,
	branch: str,
	allowed_branches: list[str],
	global_access: bool,
) -> list[str]:
	"""Return permission-aware RFQs inside the requested operating scope."""
	if not frappe.has_permission(REQUEST_FOR_QUOTATION_DOCTYPE, "read"):
		return []
	filters, _branch_field = _branch_scoped_filters(
		REQUEST_FOR_QUOTATION_DOCTYPE,
		company=company,
		branch=branch,
		allowed_branches=allowed_branches,
		global_branch_access=global_access,
	)
	return list(
		frappe.get_list(
			REQUEST_FOR_QUOTATION_DOCTYPE,
			filters=filters,
			pluck="name",
			limit_page_length=MAX_REFERENCE_SCAN,
		)
	)


def _supplier_quotation_names_from_rfqs(rfq_names: list[str]) -> list[str]:
	if not rfq_names:
		return []
	parents = frappe.get_all(
		SUPPLIER_QUOTATION_ITEM_DOCTYPE,
		filters={"request_for_quotation": ["in", rfq_names]},
		pluck="parent",
		limit_page_length=MAX_REFERENCE_SCAN * 2,
	)
	return sorted({str(parent) for parent in parents if parent})


def _linked_rfq_context(parent_names: list[str]) -> tuple[dict[str, list[str]], dict[str, str], dict[str, int]]:
	rfqs_by_parent: dict[str, list[str]] = {name: [] for name in parent_names}
	item_count_by_parent: dict[str, int] = {name: 0 for name in parent_names}
	if not parent_names:
		return rfqs_by_parent, {}, item_count_by_parent

	linked_rfqs: set[str] = set()
	for row in frappe.get_all(
		SUPPLIER_QUOTATION_ITEM_DOCTYPE,
		filters={"parent": ["in", parent_names]},
		fields=["parent", "request_for_quotation"],
		order_by="idx asc",
	):
		parent = str(row.get("parent") or "")
		if parent not in rfqs_by_parent:
			continue
		item_count_by_parent[parent] += 1
		rfq = str(row.get("request_for_quotation") or "")
		if rfq and rfq not in rfqs_by_parent[parent]:
			rfqs_by_parent[parent].append(rfq)
			linked_rfqs.add(rfq)

	branch_by_rfq: dict[str, str] = {}
	if linked_rfqs and frappe.has_permission(REQUEST_FOR_QUOTATION_DOCTYPE, "read"):
		rfq_branch_field = _transaction_branch_field(REQUEST_FOR_QUOTATION_DOCTYPE)
		fields = ["name"]
		if rfq_branch_field:
			fields.append(rfq_branch_field)
		for row in frappe.get_list(
			REQUEST_FOR_QUOTATION_DOCTYPE,
			filters={"name": ["in", sorted(linked_rfqs)]},
			fields=fields,
			limit_page_length=MAX_REFERENCE_SCAN,
		):
			name = str(row.get("name") or "")
			branch_by_rfq[name] = str(row.get(rfq_branch_field) or "") if rfq_branch_field else ""
	return rfqs_by_parent, branch_by_rfq, item_count_by_parent


def _derived_branch(rfq_names: list[str], branch_by_rfq: dict[str, str]) -> str:
	branches = sorted({branch_by_rfq.get(rfq, "") for rfq in rfq_names if branch_by_rfq.get(rfq, "")})
	if len(branches) == 1:
		return branches[0]
	if len(branches) > 1:
		return _("Multiple")
	return ""


@frappe.whitelist()
def get_supplier_quotation_history(
	company: str | None = None,
	branch: str | None = None,
	supplier: str | None = None,
	limit: int | str = 50,
) -> dict[str, Any]:
	"""Return Supplier Quotations inside permission-safe Company/Branch sourcing scope."""
	_assert_read(SUPPLIER_QUOTATION_DOCTYPE)
	resolved_company, resolved_branch, allowed_branches, global_access = _resolve_scope(
		company=company,
		branch=branch,
	)

	filters: dict[str, Any] = {"company": resolved_company}
	branch_field = _transaction_branch_field(SUPPLIER_QUOTATION_DOCTYPE)
	if branch_field:
		filters, branch_field = _branch_scoped_filters(
			SUPPLIER_QUOTATION_DOCTYPE,
			company=resolved_company,
			branch=resolved_branch,
			allowed_branches=allowed_branches,
			global_branch_access=global_access,
		)
	elif resolved_branch or not global_access:
		# Supplier Quotation has no standard Branch field in ERPNext v16. For a
		# branch-filtered or restricted user, fail closed to quotations linked to
		# RFQs that are themselves inside the permitted operating scope.
		permitted_rfqs = _permitted_rfq_names(
			company=resolved_company,
			branch=resolved_branch,
			allowed_branches=allowed_branches,
			global_access=global_access,
		)
		candidate_names = _supplier_quotation_names_from_rfqs(permitted_rfqs)
		filters["name"] = ["in", candidate_names or ["__no_permitted_supplier_quotation__"]]

	supplier = str(supplier or "").strip()
	if supplier:
		_assert_read(SUPPLIER_DOCTYPE, supplier)
		filters["supplier"] = supplier

	meta = frappe.get_meta(SUPPLIER_QUOTATION_DOCTYPE)
	fields = ["name", "docstatus", "company", "supplier", "supplier_name", "modified"]
	for fieldname in (
		"transaction_date",
		"valid_till",
		"status",
		"currency",
		"grand_total",
		"rounded_total",
		"total_qty",
		"quotation_number",
	):
		if meta.has_field(fieldname):
			fields.append(fieldname)
	if branch_field:
		fields.append(branch_field)

	row_limit = max(1, min(cint(limit) or 50, MAX_SUPPLIER_QUOTATION_HISTORY))
	rows = frappe.get_list(
		SUPPLIER_QUOTATION_DOCTYPE,
		filters=filters,
		fields=fields,
		order_by="modified desc, name desc",
		limit_page_length=row_limit,
	)
	parent_names = [str(row.get("name") or "") for row in rows if row.get("name")]
	rfqs_by_parent, branch_by_rfq, item_count_by_parent = _linked_rfq_context(parent_names)

	result_rows: list[dict[str, Any]] = []
	for row in rows:
		name = str(row.get("name") or "")
		docstatus = cint(row.get("docstatus"))
		linked_rfqs = rfqs_by_parent.get(name, [])
		row_branch = str(row.get(branch_field) or "") if branch_field else _derived_branch(linked_rfqs, branch_by_rfq)
		result_rows.append(
			{
				"name": name,
				"docstatus": docstatus,
				"status": str(row.get("status") or _docstatus_label(docstatus)),
				"company": str(row.get("company") or ""),
				"branch": row_branch,
				"supplier": str(row.get("supplier") or ""),
				"supplier_name": str(row.get("supplier_name") or row.get("supplier") or ""),
				"transaction_date": str(row.get("transaction_date") or ""),
				"valid_till": str(row.get("valid_till") or ""),
				"currency": str(row.get("currency") or ""),
				"grand_total": flt(row.get("grand_total") or row.get("rounded_total") or 0),
				"total_qty": flt(row.get("total_qty") or 0),
				"quotation_number": str(row.get("quotation_number") or ""),
				"modified": str(row.get("modified") or ""),
				"request_for_quotations": linked_rfqs,
				"item_count": item_count_by_parent.get(name, 0),
			}
		)

	return {
		"company": resolved_company,
		"branch": resolved_branch,
		"supplier": supplier,
		"rows": result_rows,
		"limit": row_limit,
		"branch_source": branch_field or "Request for Quotation linkage",
		"standalone_visibility": "company-wide only" if not branch_field and global_access and not resolved_branch else "excluded_without_attributable RFQ",
		"source_of_truth": SUPPLIER_QUOTATION_DOCTYPE,
	}
