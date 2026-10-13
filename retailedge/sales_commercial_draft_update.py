from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from retailedge.sales_commercial_terms import (
	apply_sales_commercial_terms,
	get_sales_commercial_term_capabilities,
	normalise_sales_commercial_terms,
	sales_commercial_terms_from_doc,
)
from retailedge.standard_sales_invoice_completion import (
	SALES_INVOICE_DOCTYPE,
	_build_preview,
	update_standard_sales_invoice_draft,
)


@frappe.whitelist(methods=["POST"])
def update_sales_invoice_draft_with_commercial_terms(
	name: str,
	values: dict | str | None = None,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	"""Update Make Sale draft fields and commercial terms in one request transaction.

	The existing standard completion updater retains its row lock, optimistic
	version check, operating-context validation, bounded item update and first
	ERPNext draft save. Commercial terms are then applied to that same draft and
	saved through ERPNext. Frappe commits only after the whitelisted request
	returns successfully, so a failure in the second validation rolls back the
	whole request rather than leaving a partial edit.
	"""
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if values is None:
		values = {}
	if not isinstance(values, dict):
		frappe.throw(_("Invalid Sales Invoice draft changes."), frappe.ValidationError)

	terms = normalise_sales_commercial_terms(values)
	result = update_standard_sales_invoice_draft(
		name=name,
		values=values,
		expected_modified=expected_modified,
	)
	if not terms:
		return result

	doc = frappe.get_doc(SALES_INVOICE_DOCTYPE, name)
	if cint(doc.docstatus) != 0:
		frappe.throw(_("Only draft Sales Invoices can change commercial terms."), frappe.ValidationError)
	if not frappe.has_permission(SALES_INVOICE_DOCTYPE, "read", doc=doc) or not frappe.has_permission(
		SALES_INVOICE_DOCTYPE,
		"write",
		doc=doc,
	):
		frappe.throw(_("You do not have permission to edit this Sales Invoice."), frappe.PermissionError)

	apply_sales_commercial_terms(doc, terms)
	# ERPNext validation recalculates pricing rules, discounts, tax and totals.
	# This remains a draft save; no submission, ledger post or explicit commit
	# occurs in this adapter.
	doc.save()
	doc.reload()

	result = _build_preview(doc)
	result["commercial_terms"] = sales_commercial_terms_from_doc(doc)
	result["commercial_term_capabilities"] = get_sales_commercial_term_capabilities(doc)
	result["persistence"] = "draft_update"
	return result
