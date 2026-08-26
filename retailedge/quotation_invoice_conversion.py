from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable

import frappe
from frappe import _
from frappe.utils import now_datetime

CONVERSION_DOCTYPE = "RetailEdge Quotation Invoice Conversion"
_CONVERSION_FLAG = "retailedge_direct_quote_invoice_conversion"


def assert_conversion_registry_available() -> None:
	if frappe.db.exists("DocType", CONVERSION_DOCTYPE):
		return
	frappe.throw(
		_(
			"RetailEdge direct Quotation to Sales Invoice tracking is not installed on this site. "
			"Run bench migrate before using direct quotation invoicing."
		)
	)


def get_quotation_conversion(quotation: str) -> dict[str, Any] | None:
	assert_conversion_registry_available()
	name = frappe.db.get_value(CONVERSION_DOCTYPE, {"quotation": quotation}, "name")
	if not name:
		return None
	return frappe.db.get_value(
		CONVERSION_DOCTYPE,
		name,
		["name", "quotation", "sales_invoice", "company", "branch", "converted_by", "converted_on"],
		as_dict=True,
	)


def quotation_has_conversion(quotation: str) -> bool:
	return bool(get_quotation_conversion(quotation))


def filter_unconverted_quotation_results(rows: Iterable[Any], *, limit: int) -> list[Any]:
	"""Filter a bounded permission-aware Quotation search without loading the full table."""
	assert_conversion_registry_available()
	results: list[Any] = []
	for row in rows:
		quotation = _search_result_value(row)
		if quotation and quotation_has_conversion(quotation):
			continue
		results.append(row)
		if len(results) >= limit:
			break
	return results


def reserve_quotation_conversion(source, *, company: str, branch: str) -> Any:
	"""Reserve one direct-conversion identity before inserting the invoice.

	The registry DocType is named from the Quotation, so the database primary key
	is the concurrency boundary. Two simultaneous requests cannot reserve the same
	Quotation. The reservation and Sales Invoice insert share the request
	transaction; no manual commit is performed.
	"""
	assert_conversion_registry_available()
	existing = get_quotation_conversion(source.name)
	if existing:
		_throw_already_converted(source.name, existing.get("sales_invoice"))

	tracker = frappe.new_doc(CONVERSION_DOCTYPE)
	tracker.quotation = source.name
	tracker.company = company
	tracker.branch = branch or ""
	tracker.converted_by = frappe.session.user
	tracker.converted_on = now_datetime()
	try:
		with _conversion_write_scope():
			tracker.insert()
	except frappe.DuplicateEntryError:
		existing = get_quotation_conversion(source.name) or {}
		_throw_already_converted(source.name, existing.get("sales_invoice"))
	return tracker


def complete_quotation_conversion(tracker, sales_invoice: str) -> None:
	if not tracker or tracker.doctype != CONVERSION_DOCTYPE:
		frappe.throw(_("RetailEdge could not complete the quotation conversion audit record."))
	with _conversion_write_scope():
		tracker.sales_invoice = sales_invoice
		tracker.save()


def conversion_write_authorized() -> bool:
	return bool(getattr(frappe.flags, _CONVERSION_FLAG, False))


@contextmanager
def _conversion_write_scope():
	previous = getattr(frappe.flags, _CONVERSION_FLAG, False)
	setattr(frappe.flags, _CONVERSION_FLAG, True)
	try:
		yield
	finally:
		setattr(frappe.flags, _CONVERSION_FLAG, previous)


def _search_result_value(row: Any) -> str:
	if isinstance(row, dict):
		return str(row.get("value") or row.get("name") or "").strip()
	if isinstance(row, (list, tuple)) and row:
		return str(row[0] or "").strip()
	return str(row or "").strip()


def _throw_already_converted(quotation: str, sales_invoice: str | None) -> None:
	if sales_invoice:
		frappe.throw(
		_(
			"Quotation {0} already created direct Sales Invoice {1}. Open that invoice instead; "
			"if it was cancelled, use ERPNext Amend rather than converting the quotation again."
		).format(quotation, sales_invoice)
		)
	frappe.throw(
		_(
			"Quotation {0} already has a RetailEdge direct-invoice conversion reservation. "
			"Do not create a second invoice from the same quotation."
		).format(quotation)
	)
