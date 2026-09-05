from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt

from erpnext.controllers.stock_controller import (
	check_item_quality_inspection,
	make_quality_inspections,
)

from retailedge.professional_purchasing import (
	MAX_LINK_RESULTS,
	PURCHASE_RECEIPT_DOCTYPE,
	SUPPLIER_DOCTYPE,
	_assert_create,
	_assert_read,
	_branch_scoped_filters,
	_document_branch,
	_permission,
	_resolve_scope,
)

QUALITY_INSPECTION_DOCTYPE = "Quality Inspection"
MAX_QUALITY_INSPECTION_ROWS = 50
_ALLOWED_SELECTION_KEYS = {"child_row_reference", "sample_size"}


def _assert_quality_permissions() -> None:
	if not _permission(PURCHASE_RECEIPT_DOCTYPE, "read"):
		frappe.throw(
			_("You do not have permission to read Purchase Receipt."),
			frappe.PermissionError,
		)
	_assert_create(QUALITY_INSPECTION_DOCTYPE)


def _validate_draft_receipt(receipt: Any) -> tuple[str, str]:
	"""Validate one persisted draft receipt against the current operating scope."""
	if getattr(receipt, "doctype", None) != PURCHASE_RECEIPT_DOCTYPE:
		frappe.throw(_("Incoming Quality Inspection requires a Purchase Receipt."))
	if cint(getattr(receipt, "docstatus", 0)) != 0:
		frappe.throw(_("Guided Incoming Quality Inspection is available only for draft Purchase Receipts."))
	if cint(getattr(receipt, "is_return", 0)):
		frappe.throw(_("Return Purchase Receipts are not valid sources for Incoming Quality Inspection."))
	if not str(getattr(receipt, "name", "") or "").strip():
		frappe.throw(_("Save the Purchase Receipt before preparing Quality Inspections."))

	company = str(getattr(receipt, "company", "") or "").strip()
	if not company:
		frappe.throw(_("The selected Purchase Receipt has no Company."))
	branch = _document_branch(receipt)
	resolved_company, resolved_branch, _allowed, _global_access = _resolve_scope(
		company=company,
		branch=branch,
	)
	if resolved_company != company:
		frappe.throw(_("The selected Purchase Receipt does not match the current Operating Company."))
	if resolved_branch and branch != resolved_branch:
		frappe.throw(
			_("The selected Purchase Receipt is not attributed to the current Operating Branch.")
		)
	return company, branch


def _authoritative_candidate_rows(receipt: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
	"""Build native ERPNext candidate rows from the authoritative Purchase Receipt."""
	candidates: list[dict[str, Any]] = []
	rows_by_name: dict[str, Any] = {}
	for row in list(getattr(receipt, "items", None) or []):
		row_name = str(getattr(row, "name", "") or "").strip()
		item_code = str(getattr(row, "item_code", "") or "").strip()
		qty = flt(getattr(row, "qty", 0))
		if not row_name or not item_code or qty <= 0:
			continue
		if str(getattr(row, "quality_inspection", "") or "").strip():
			continue

		rows_by_name[row_name] = row
		candidates.append(
			{
				"item_code": item_code,
				"item_name": str(getattr(row, "item_name", "") or item_code),
				"qty": qty,
				"description": str(getattr(row, "description", "") or ""),
				"serial_no": str(getattr(row, "serial_no", "") or ""),
				"batch_no": str(getattr(row, "batch_no", "") or ""),
				"child_row_reference": row_name,
				"quality_inspection": "",
			}
		)
	return candidates, rows_by_name


def _eligible_rows(receipt: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
	candidates, rows_by_name = _authoritative_candidate_rows(receipt)
	if not candidates:
		return [], rows_by_name

	eligible = list(
		check_item_quality_inspection(
			PURCHASE_RECEIPT_DOCTYPE,
			cint(getattr(receipt, "docstatus", 0)),
			candidates,
		)
		or []
	)
	eligible_names = {
		str(row.get("child_row_reference") or "").strip()
		for row in eligible
		if row.get("child_row_reference")
	}
	return [row for row in candidates if row["child_row_reference"] in eligible_names], rows_by_name


def _suggested_sample_size(row: Any, qty: float) -> float:
	suggested = flt(getattr(row, "sample_quantity", 0))
	if suggested <= 0 or suggested > qty:
		suggested = min(1.0, qty)
	return suggested


def _normalise_selections(selections: list[Any] | str | None) -> list[dict[str, Any]]:
	if isinstance(selections, str):
		try:
			selections = frappe.parse_json(selections)
		except Exception:
			selections = None
	if not isinstance(selections, (list, tuple)) or not selections:
		frappe.throw(_("Select at least one Purchase Receipt item for Quality Inspection."))
	if len(selections) > MAX_QUALITY_INSPECTION_ROWS:
		frappe.throw(
			_("A single guided Quality Inspection action can include at most {0} receipt rows.").format(
				MAX_QUALITY_INSPECTION_ROWS
			)
		)

	normalised: list[dict[str, Any]] = []
	seen: set[str] = set()
	for value in selections:
		if not isinstance(value, dict):
			frappe.throw(_("Quality Inspection selections must contain receipt row and sample size only."))
		unexpected = set(value) - _ALLOWED_SELECTION_KEYS
		if unexpected:
			frappe.throw(_("Quality Inspection selections contain unsupported authoritative fields."))
		row_name = str(value.get("child_row_reference") or "").strip()
		if not row_name:
			frappe.throw(_("A selected Purchase Receipt row is missing."))
		if row_name in seen:
			frappe.throw(_("Purchase Receipt row {0} was selected more than once.").format(row_name))
		seen.add(row_name)
		normalised.append(
			{
				"child_row_reference": row_name,
				"sample_size": flt(value.get("sample_size")),
			}
		)
	return normalised


@frappe.whitelist()
def get_incoming_quality_capability() -> dict[str, Any]:
	"""Return permission-aware C19 capability for Professional Purchasing."""
	can_read_receipt = _permission(PURCHASE_RECEIPT_DOCTYPE, "read")
	can_create_quality_inspection = _permission(QUALITY_INSPECTION_DOCTYPE, "create")
	return {
		"can_prepare_incoming_quality": bool(can_read_receipt and can_create_quality_inspection),
		"can_read_purchase_receipt": bool(can_read_receipt),
		"can_create_quality_inspection": bool(can_create_quality_inspection),
		"max_rows": MAX_QUALITY_INSPECTION_ROWS,
		"source_of_truth": "ERPNext Purchase Receipt and native Quality Inspection",
	}


@frappe.whitelist()
def search_incoming_quality_receipts(
	txt: str = "",
	company: str | None = None,
	branch: str | None = None,
	supplier: str | None = None,
) -> list[dict[str, Any]]:
	"""Search persisted draft Purchase Receipts inside authorised operating scope."""
	_assert_quality_permissions()
	resolved_company, resolved_branch, allowed, global_access = _resolve_scope(
		company=company,
		branch=branch,
	)
	filters, _branch_field = _branch_scoped_filters(
		PURCHASE_RECEIPT_DOCTYPE,
		company=resolved_company,
		branch=resolved_branch,
		allowed_branches=allowed,
		global_branch_access=global_access,
	)
	filters.update({"docstatus": 0, "is_return": 0})

	supplier = str(supplier or "").strip()
	if supplier:
		_assert_read(SUPPLIER_DOCTYPE, supplier)
		filters["supplier"] = supplier

	return list(
		search_link(
			PURCHASE_RECEIPT_DOCTYPE,
			str(txt or "").strip(),
			filters=filters,
			page_length=MAX_LINK_RESULTS,
			reference_doctype=QUALITY_INSPECTION_DOCTYPE,
			link_fieldname="reference_name",
		)
	)


@frappe.whitelist()
def get_incoming_quality_receipt_context(purchase_receipt: str) -> dict[str, Any]:
	"""Return only ERPNext-eligible incoming-inspection rows for one draft receipt."""
	purchase_receipt = str(purchase_receipt or "").strip()
	if not purchase_receipt:
		frappe.throw(_("Purchase Receipt is required."))
	_assert_read(PURCHASE_RECEIPT_DOCTYPE, purchase_receipt)
	_assert_create(QUALITY_INSPECTION_DOCTYPE)

	receipt = frappe.get_doc(PURCHASE_RECEIPT_DOCTYPE, purchase_receipt)
	company, branch = _validate_draft_receipt(receipt)
	eligible, rows_by_name = _eligible_rows(receipt)

	items: list[dict[str, Any]] = []
	for candidate in eligible:
		row = rows_by_name[candidate["child_row_reference"]]
		qty = flt(candidate["qty"])
		items.append(
			{
				"child_row_reference": candidate["child_row_reference"],
				"item_code": candidate["item_code"],
				"item_name": candidate["item_name"],
				"qty": qty,
				"uom": str(getattr(row, "uom", "") or getattr(row, "stock_uom", "") or ""),
				"warehouse": str(getattr(row, "warehouse", "") or ""),
				"batch_no": candidate["batch_no"],
				"has_serial_no": bool(candidate["serial_no"]),
				"suggested_sample_size": _suggested_sample_size(row, qty),
			}
		)

	return {
		"purchase_receipt": receipt.name,
		"company": company,
		"branch": branch,
		"supplier": str(getattr(receipt, "supplier", "") or ""),
		"supplier_name": str(getattr(receipt, "supplier_name", "") or ""),
		"posting_date": getattr(receipt, "posting_date", None),
		"items": items,
		"eligible_count": len(items),
		"source_of_truth": "ERPNext check_item_quality_inspection",
	}


@frappe.whitelist(methods=["POST"])
def create_incoming_quality_inspections(
	purchase_receipt: str,
	selections: list[Any] | str | None = None,
) -> dict[str, Any]:
	"""Create native ERPNext draft Quality Inspections for selected draft receipt rows."""
	purchase_receipt = str(purchase_receipt or "").strip()
	if not purchase_receipt:
		frappe.throw(_("Purchase Receipt is required."))
	normalised = _normalise_selections(selections)

	_assert_read(PURCHASE_RECEIPT_DOCTYPE, purchase_receipt)
	_assert_create(QUALITY_INSPECTION_DOCTYPE)
	receipt = frappe.get_doc(PURCHASE_RECEIPT_DOCTYPE, purchase_receipt)
	company, branch = _validate_draft_receipt(receipt)
	eligible, rows_by_name = _eligible_rows(receipt)
	eligible_by_name = {row["child_row_reference"]: row for row in eligible}

	native_rows: list[dict[str, Any]] = []
	for selection in normalised:
		row_name = selection["child_row_reference"]
		candidate = eligible_by_name.get(row_name)
		row = rows_by_name.get(row_name)
		if not candidate or not row:
			frappe.throw(
				_("Purchase Receipt row {0} is no longer eligible for Incoming Quality Inspection.").format(
					row_name
				)
			)
		qty = flt(candidate["qty"])
		sample_size = flt(selection["sample_size"])
		if sample_size <= 0:
			frappe.throw(_("Sample Size must be greater than zero for Item {0}.").format(candidate["item_code"]))
		if sample_size > qty:
			frappe.throw(
				_("Sample Size for Item {0} cannot exceed the accepted Purchase Receipt quantity.").format(
					candidate["item_code"]
				)
			)

		native_rows.append(
			{
				"item_code": candidate["item_code"],
				"item_name": candidate["item_name"],
				"qty": qty,
				"description": candidate["description"],
				"serial_no": candidate["serial_no"],
				"batch_no": candidate["batch_no"],
				"sample_size": sample_size,
				"child_row_reference": row_name,
			}
		)

	created = list(
		make_quality_inspections(
			company=company,
			doctype=PURCHASE_RECEIPT_DOCTYPE,
			docname=receipt.name,
			items=native_rows,
			inspection_type="Incoming",
		)
		or []
	)
	if len(created) != len(native_rows):
		frappe.throw(_("ERPNext did not create the expected number of draft Quality Inspections."))

	return {
		"purchase_receipt": receipt.name,
		"company": company,
		"branch": branch,
		"created": [
			{
				"name": str(name),
				"doctype": QUALITY_INSPECTION_DOCTYPE,
				"docstatus": 0,
				"posting_status": "Draft",
				"route": f"/app/quality-inspection/{name}",
			}
			for name in created
		],
		"created_count": len(created),
		"source_of_truth": "ERPNext make_quality_inspections",
	}
