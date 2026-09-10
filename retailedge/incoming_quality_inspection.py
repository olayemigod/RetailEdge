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
_ALLOWED_REVIEW_SELECTION_KEYS = {"child_row_reference", "sample_size", "readings"}
_READING_INPUT_FIELDS = tuple(["reading_value", *[f"reading_{index}" for index in range(1, 11)]])
_ALLOWED_READING_KEYS = {"idx", "specification", *_READING_INPUT_FIELDS}


def _assert_quality_permissions() -> None:
	if not _permission(PURCHASE_RECEIPT_DOCTYPE, "read"):
		frappe.throw(
			_("You do not have permission to read Purchase Receipt."),
			frappe.PermissionError,
		)
	_assert_create(QUALITY_INSPECTION_DOCTYPE)


def _assert_quality_submit_permission() -> None:
	_assert_quality_permissions()
	if not _permission(QUALITY_INSPECTION_DOCTYPE, "submit"):
		frappe.throw(
			_("You do not have permission to submit Quality Inspection."),
			frappe.PermissionError,
		)


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


def _parse_list_payload(value: list[Any] | str | None, *, empty_message: str) -> list[Any]:
	if isinstance(value, str):
		try:
			value = frappe.parse_json(value)
		except Exception:
			value = None
	if not isinstance(value, (list, tuple)) or not value:
		frappe.throw(_(empty_message))
	if len(value) > MAX_QUALITY_INSPECTION_ROWS:
		frappe.throw(
			_("A single guided Quality Inspection action can include at most {0} receipt rows.").format(
				MAX_QUALITY_INSPECTION_ROWS
			)
		)
	return list(value)


def _normalise_selections(selections: list[Any] | str | None) -> list[dict[str, Any]]:
	values = _parse_list_payload(
		selections,
		empty_message="Select at least one Purchase Receipt item for Quality Inspection.",
	)
	normalised: list[dict[str, Any]] = []
	seen: set[str] = set()
	for value in values:
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


def _normalise_review_submissions(selections: list[Any] | str | None) -> list[dict[str, Any]]:
	values = _parse_list_payload(
		selections,
		empty_message="Quality Inspection review values are required.",
	)
	normalised: list[dict[str, Any]] = []
	seen_rows: set[str] = set()
	for value in values:
		if not isinstance(value, dict):
			frappe.throw(_("Quality Inspection review selections must be objects."))
		unexpected = set(value) - _ALLOWED_REVIEW_SELECTION_KEYS
		if unexpected:
			frappe.throw(_("Quality Inspection review contains unsupported authoritative fields."))
		row_name = str(value.get("child_row_reference") or "").strip()
		if not row_name:
			frappe.throw(_("A reviewed Purchase Receipt row is missing."))
		if row_name in seen_rows:
			frappe.throw(_("Purchase Receipt row {0} was reviewed more than once.").format(row_name))
		seen_rows.add(row_name)

		reading_values = value.get("readings")
		if isinstance(reading_values, str):
			try:
				reading_values = frappe.parse_json(reading_values)
			except Exception:
				reading_values = None
		if not isinstance(reading_values, (list, tuple)):
			frappe.throw(_("Quality Inspection readings must be supplied as a list."))

		readings: list[dict[str, Any]] = []
		seen_indexes: set[int] = set()
		for reading in reading_values:
			if not isinstance(reading, dict):
				frappe.throw(_("Each Quality Inspection reading must be an object."))
			unexpected_reading = set(reading) - _ALLOWED_READING_KEYS
			if unexpected_reading:
				frappe.throw(_("Quality Inspection readings contain unsupported criteria or status fields."))
			idx = cint(reading.get("idx"))
			specification = str(reading.get("specification") or "").strip()
			if idx <= 0 or not specification:
				frappe.throw(_("Each Quality Inspection reading must identify its current template row."))
			if idx in seen_indexes:
				frappe.throw(_("Quality Inspection reading row {0} was supplied more than once.").format(idx))
			seen_indexes.add(idx)
			normalised_reading = {"idx": idx, "specification": specification}
			for fieldname in _READING_INPUT_FIELDS:
				if fieldname in reading:
					normalised_reading[fieldname] = reading.get(fieldname)
			readings.append(normalised_reading)

		normalised.append(
			{
				"child_row_reference": row_name,
				"sample_size": flt(value.get("sample_size")),
				"readings": readings,
			}
		)
	return normalised


def _validate_sample_size(candidate: dict[str, Any], sample_size: float) -> float:
	qty = flt(candidate.get("qty"))
	item_code = str(candidate.get("item_code") or "")
	if sample_size <= 0:
		frappe.throw(_("Sample Size must be greater than zero for Item {0}.").format(item_code))
	if sample_size > qty:
		frappe.throw(
			_("Sample Size for Item {0} cannot exceed the accepted Purchase Receipt quantity.").format(
				item_code
			)
		)
	return sample_size


def _get_receipt(purchase_receipt: str, *, lock: bool = False) -> Any:
	name = str(purchase_receipt or "").strip()
	if not name:
		frappe.throw(_("Purchase Receipt is required."))
	_assert_read(PURCHASE_RECEIPT_DOCTYPE, name)
	_assert_create(QUALITY_INSPECTION_DOCTYPE)
	if lock:
		frappe.db.sql(
			"SELECT name FROM `tabPurchase Receipt` WHERE name = %s FOR UPDATE",
			(name,),
		)
	receipt = frappe.get_doc(PURCHASE_RECEIPT_DOCTYPE, name)
	_validate_draft_receipt(receipt)
	return receipt


def _quality_inspection_for_candidate(
	receipt: Any,
	candidate: dict[str, Any],
	*,
	sample_size: float,
) -> Any:
	serial_no = str(candidate.get("serial_no") or "")
	quality_inspection = frappe.get_doc(
		{
			"doctype": QUALITY_INSPECTION_DOCTYPE,
			"company": str(getattr(receipt, "company", "") or ""),
			"inspection_type": "Incoming",
			"inspected_by": frappe.session.user,
			"reference_type": PURCHASE_RECEIPT_DOCTYPE,
			"reference_name": receipt.name,
			"item_code": candidate.get("item_code"),
			"description": candidate.get("description"),
			"sample_size": sample_size,
			"item_serial_no": serial_no.split("\n")[0] if serial_no else None,
			"batch_no": candidate.get("batch_no"),
			"child_row_reference": candidate.get("child_row_reference"),
		}
	)
	quality_inspection.get_item_specification_details()
	return quality_inspection


def _inspection_blockers(quality_inspection: Any) -> list[dict[str, str]]:
	item_code = str(getattr(quality_inspection, "item_code", "") or "")
	if not str(getattr(quality_inspection, "quality_inspection_template", "") or "").strip():
		return [
			{
				"key": "missing_template",
				"item_code": item_code,
				"label": _("No Quality Inspection Template is configured; use Advanced ERPNext"),
			}
		]
	readings = list(getattr(quality_inspection, "readings", None) or [])
	if not readings:
		return [
			{
				"key": "missing_specifications",
				"item_code": item_code,
				"label": _("The Quality Inspection Template has no specification rows; use Advanced ERPNext"),
			}
		]
	if cint(getattr(quality_inspection, "manual_inspection", 0)) or any(
		cint(getattr(reading, "manual_inspection", 0)) for reading in readings
	):
		return [
			{
				"key": "manual_inspection",
				"item_code": item_code,
				"label": _("Manual inspection status requires Advanced ERPNext"),
			}
		]
	return []


def _serialise_reading(reading: Any, idx: int) -> dict[str, Any]:
	return {
		"idx": idx,
		"specification": str(getattr(reading, "specification", "") or ""),
		"parameter_group": str(getattr(reading, "parameter_group", "") or ""),
		"numeric": bool(cint(getattr(reading, "numeric", 0))),
		"formula_based_criteria": bool(cint(getattr(reading, "formula_based_criteria", 0))),
		"min_value": flt(getattr(reading, "min_value", 0)),
		"max_value": flt(getattr(reading, "max_value", 0)),
		"value": str(getattr(reading, "value", "") or ""),
		"acceptance_formula": str(getattr(reading, "acceptance_formula", "") or ""),
		"reading_value": "",
		**{f"reading_{number}": "" for number in range(1, 11)},
	}


def _review_item(
	receipt: Any,
	candidate: dict[str, Any],
	row: Any,
	*,
	sample_size: float,
) -> dict[str, Any]:
	quality_inspection = _quality_inspection_for_candidate(
		receipt,
		candidate,
		sample_size=sample_size,
	)
	blockers = _inspection_blockers(quality_inspection)
	return {
		"child_row_reference": candidate["child_row_reference"],
		"item_code": candidate["item_code"],
		"item_name": candidate["item_name"],
		"qty": flt(candidate["qty"]),
		"uom": str(getattr(row, "uom", "") or getattr(row, "stock_uom", "") or ""),
		"warehouse": str(getattr(row, "warehouse", "") or ""),
		"batch_no": str(candidate.get("batch_no") or ""),
		"has_serial_no": bool(candidate.get("serial_no")),
		"sample_size": sample_size,
		"quality_inspection_template": str(
			getattr(quality_inspection, "quality_inspection_template", "") or ""
		),
		"readings": [
			_serialise_reading(reading, idx)
			for idx, reading in enumerate(list(getattr(quality_inspection, "readings", None) or []), start=1)
		],
		"blockers": blockers,
		"standard_submit_eligible": not blockers,
	}


def _apply_review_readings(quality_inspection: Any, submitted: list[dict[str, Any]]) -> None:
	authoritative = list(getattr(quality_inspection, "readings", None) or [])
	if len(authoritative) != len(submitted):
		frappe.throw(_("Quality Inspection template changed after preview. Refresh before submitting."))
	submitted_by_idx = {cint(value.get("idx")): value for value in submitted}
	for idx, reading in enumerate(authoritative, start=1):
		value = submitted_by_idx.get(idx)
		specification = str(getattr(reading, "specification", "") or "")
		if not value or str(value.get("specification") or "") != specification:
			frappe.throw(_("Quality Inspection template changed after preview. Refresh before submitting."))

		if cint(getattr(reading, "manual_inspection", 0)):
			frappe.throw(_("Manual inspection status requires Advanced ERPNext."))

		if cint(getattr(reading, "numeric", 0)):
			if str(value.get("reading_value") or "").strip():
				frappe.throw(_("Numeric Quality Inspection rows accept numeric Reading fields only."))
			has_reading = False
			for number in range(1, 11):
				fieldname = f"reading_{number}"
				reading_value = value.get(fieldname)
				if reading_value is None:
					reading_value = ""
				reading_value = str(reading_value)
				if reading_value.strip():
					has_reading = True
				setattr(reading, fieldname, reading_value)
			if not has_reading:
				frappe.throw(_("Enter at least one numeric reading for {0}.").format(specification))
		else:
			for number in range(1, 11):
				if str(value.get(f"reading_{number}") or "").strip():
					frappe.throw(_("Value-based Quality Inspection rows accept Reading Value only."))
			reading_value = str(value.get("reading_value") or "").strip()
			if not reading_value:
				frappe.throw(_("Enter Reading Value for {0}.").format(specification))
			reading.reading_value = reading_value


@frappe.whitelist()
def get_incoming_quality_capability() -> dict[str, Any]:
	"""Return permission-aware C19/F3F18 capability for Professional Purchasing."""
	can_read_receipt = _permission(PURCHASE_RECEIPT_DOCTYPE, "read")
	can_create_quality_inspection = _permission(QUALITY_INSPECTION_DOCTYPE, "create")
	can_submit_quality_inspection = _permission(QUALITY_INSPECTION_DOCTYPE, "submit")
	return {
		"can_prepare_incoming_quality": bool(can_read_receipt and can_create_quality_inspection),
		"can_read_purchase_receipt": bool(can_read_receipt),
		"can_create_quality_inspection": bool(can_create_quality_inspection),
		"can_submit_quality_inspection": bool(can_submit_quality_inspection),
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
		"source_modified": str(getattr(receipt, "modified", "") or ""),
		"company": company,
		"branch": branch,
		"supplier": str(getattr(receipt, "supplier", "") or ""),
		"supplier_name": str(getattr(receipt, "supplier_name", "") or ""),
		"posting_date": getattr(receipt, "posting_date", None),
		"items": items,
		"eligible_count": len(items),
		"source_of_truth": "ERPNext check_item_quality_inspection",
	}


@frappe.whitelist()
def get_incoming_quality_inspection_review(
	purchase_receipt: str,
	selections: list[Any] | str | None = None,
) -> dict[str, Any]:
	"""Build an unsaved ERPNext Quality Inspection review for selected receipt rows."""
	normalised = _normalise_selections(selections)
	receipt = _get_receipt(purchase_receipt)
	company, branch = _validate_draft_receipt(receipt)
	eligible, rows_by_name = _eligible_rows(receipt)
	eligible_by_name = {row["child_row_reference"]: row for row in eligible}

	items: list[dict[str, Any]] = []
	blockers: list[dict[str, str]] = []
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
		sample_size = _validate_sample_size(candidate, flt(selection["sample_size"]))
		item_review = _review_item(receipt, candidate, row, sample_size=sample_size)
		items.append(item_review)
		blockers.extend(item_review["blockers"])

	return {
		"purchase_receipt": receipt.name,
		"source_modified": str(getattr(receipt, "modified", "") or ""),
		"company": company,
		"branch": branch,
		"supplier": str(getattr(receipt, "supplier", "") or ""),
		"supplier_name": str(getattr(receipt, "supplier_name", "") or ""),
		"items": items,
		"blockers": blockers,
		"standard_submit_eligible": not blockers,
		"can_submit": bool(not blockers and _permission(QUALITY_INSPECTION_DOCTYPE, "submit")),
		"persistence": "none",
		"posting_status": "Preview only",
		"source_of_truth": "ERPNext Quality Inspection template",
	}


@frappe.whitelist(methods=["POST"])
def submit_incoming_quality_inspection_review(
	purchase_receipt: str,
	expected_source_modified: str | None = None,
	selections: list[Any] | str | None = None,
) -> dict[str, Any]:
	"""Insert and submit the reviewed standard Quality Inspections using ERPNext lifecycle rules."""
	normalised = _normalise_review_submissions(selections)
	_assert_quality_submit_permission()
	receipt = _get_receipt(purchase_receipt, lock=True)
	company, branch = _validate_draft_receipt(receipt)

	expected_modified = str(expected_source_modified or "").strip()
	current_modified = str(getattr(receipt, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(
			_("Purchase Receipt {0} changed after the Quality Inspection preview. Refresh before submitting.").format(
				receipt.name
			)
		)

	eligible, rows_by_name = _eligible_rows(receipt)
	eligible_by_name = {row["child_row_reference"]: row for row in eligible}
	created: list[dict[str, Any]] = []
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
		sample_size = _validate_sample_size(candidate, flt(selection["sample_size"]))
		quality_inspection = _quality_inspection_for_candidate(
			receipt,
			candidate,
			sample_size=sample_size,
		)
		blockers = _inspection_blockers(quality_inspection)
		if blockers:
			labels = ", ".join(str(blocker.get("label") or blocker.get("key") or "") for blocker in blockers)
			frappe.throw(_("This Quality Inspection requires Advanced ERPNext handling: {0}").format(labels))

		_apply_review_readings(quality_inspection, selection["readings"])

		# ERPNext remains authoritative. Validation computes each reading status and
		# the final Accepted/Rejected inspection status; normal insert/submit updates
		# the Purchase Receipt child-row Quality Inspection reference.
		quality_inspection.insert()
		quality_inspection.submit()
		if cint(getattr(quality_inspection, "docstatus", 0)) != 1:
			frappe.throw(
				_("ERPNext did not submit Quality Inspection {0}.").format(quality_inspection.name)
			)
		created.append(
			{
				"doctype": QUALITY_INSPECTION_DOCTYPE,
				"name": quality_inspection.name,
				"docstatus": cint(quality_inspection.docstatus),
				"status": str(getattr(quality_inspection, "status", "") or ""),
				"child_row_reference": row_name,
				"item_code": candidate["item_code"],
			}
		)

	return {
		"purchase_receipt": receipt.name,
		"company": company,
		"branch": branch,
		"created": created,
		"created_count": len(created),
		"posting_status": "Submitted",
		"source_of_truth": "ERPNext Quality Inspection validate and submit",
	}


@frappe.whitelist(methods=["POST"])
def create_incoming_quality_inspections(
	purchase_receipt: str,
	selections: list[Any] | str | None = None,
) -> dict[str, Any]:
	"""Advanced compatibility: create native ERPNext draft Quality Inspections."""
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
		sample_size = _validate_sample_size(candidate, flt(selection["sample_size"]))

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
