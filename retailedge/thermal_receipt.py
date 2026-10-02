from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.branch_context import BRANCH_FIELD_CANDIDATES
from retailedge.document_output import _assert_document_permission, get_output_document_definition

SUPPORTED_THERMAL_RECEIPT_DOCTYPES = {"Sales Invoice", "POS Invoice"}


def _text(value: Any) -> str:
	return str(value or "").strip()


def _money(value: Any, currency: str) -> str:
	return f"{currency} {flt(value):,.2f}".strip()


def _quantity(value: Any) -> str:
	qty = flt(value)
	return f"{qty:,.0f}" if qty.is_integer() else f"{qty:,.3f}".rstrip("0").rstrip(".")


def _branch(doc) -> str:
	for fieldname in BRANCH_FIELD_CANDIDATES:
		if doc.meta.has_field(fieldname):
			value = _text(doc.get(fieldname))
			if value:
				return value
	return ""


def _item_label(row) -> str:
	return _text(row.get("item_name") or row.get("item_code") or row.get("description")) or _("Item")


def _item_blocks(doc, currency: str) -> list[dict[str, Any]]:
	blocks: list[dict[str, Any]] = []
	for row in doc.get("items") or []:
		blocks.append({"type": "text", "text": _item_label(row), "bold": True})
		blocks.append(
			{
				"type": "text",
				"text": _("{0} x {1}").format(
					_quantity(row.get("qty")),
					_money(row.get("rate"), currency),
				),
			}
		)
		# Preserve the complete monetary amount on narrow 58 mm paper. EdgeSuite
		# may wrap text blocks, while row cells are intentionally width-bounded.
		blocks.append(
			{
				"type": "text",
				"text": _money(row.get("amount"), currency),
				"align": "right",
			}
		)
	return blocks


def _payment_blocks(doc, currency: str) -> list[dict[str, Any]]:
	blocks: list[dict[str, Any]] = []
	payments = doc.get("payments") if doc.meta.has_field("payments") else []
	for payment in payments or []:
		amount = flt(payment.get("amount"))
		if not amount:
			continue
		label = _text(payment.get("mode_of_payment")) or _("Payment")
		blocks.append(
			{
				"type": "text",
				"text": _("{0}: {1}").format(label, _money(amount, currency)),
			}
		)
	return blocks


def _receipt_blocks(doc, definition: dict[str, Any]) -> list[dict[str, Any]]:
	currency = _text(doc.get("currency")) or "NGN"
	company = _text(doc.get("company"))
	branch = _branch(doc)
	party = _text(doc.get(definition.get("party_field")))
	posting_date = _text(doc.get(definition.get("date_field")))
	blocks: list[dict[str, Any]] = []

	if company:
		blocks.append({"type": "text", "text": company, "align": "center", "bold": True})
	if branch:
		blocks.append({"type": "text", "text": branch, "align": "center"})
	blocks.extend(
		[
			{"type": "text", "text": definition["label"], "align": "center", "bold": True},
			{"type": "text", "text": doc.name, "align": "center"},
			{"type": "rule"},
		]
	)
	if posting_date:
		blocks.append({"type": "row", "columns": [{"text": _("Date")}, {"text": posting_date, "align": "right"}]})
	if party:
		blocks.append({"type": "text", "text": _("Customer: {0}").format(party)})
	blocks.append({"type": "rule"})
	blocks.extend(_item_blocks(doc, currency))
	blocks.append({"type": "rule"})

	if doc.meta.has_field("net_total"):
		blocks.append(
			{
				"type": "text",
				"text": _("Subtotal: {0}").format(_money(doc.get("net_total"), currency)),
			}
		)
	if doc.meta.has_field("total_taxes_and_charges") and flt(doc.get("total_taxes_and_charges")):
		blocks.append(
			{
				"type": "text",
				"text": _("Tax / Charges: {0}").format(
					_money(doc.get("total_taxes_and_charges"), currency)
				),
			}
		)
	blocks.extend(
		[
			{
				"type": "text",
				"text": _("TOTAL: {0}").format(_money(doc.get("grand_total"), currency)),
				"bold": True,
			},
			{"type": "rule"},
		]
	)

	payment_blocks = _payment_blocks(doc, currency)
	if payment_blocks:
		blocks.append({"type": "text", "text": _("Payment"), "bold": True})
		blocks.extend(payment_blocks)
	elif doc.meta.has_field("outstanding_amount"):
		blocks.append(
			{
				"type": "text",
				"text": _("Outstanding: {0}").format(
					_money(doc.get("outstanding_amount"), currency)
				),
			}
		)

	blocks.extend(
		[
			{"type": "rule"},
			{"type": "text", "text": _("Thank you"), "align": "center"},
			{"type": "qr", "value": f"{definition['doctype']}:{doc.name}", "align": "center", "size": 4},
		]
	)
	return blocks


@frappe.whitelist(methods=["GET"])
def get_thermal_receipt_payload(document: str, name: str) -> dict[str, Any]:
	"""Return a product-owned logical receipt for EdgeSuite's shared printer runtime."""

	definition = get_output_document_definition(document)
	doctype = definition["doctype"]
	if doctype not in SUPPORTED_THERMAL_RECEIPT_DOCTYPES:
		frappe.throw(_("{0} does not support direct thermal receipt printing.").format(doctype))

	_assert_document_permission(doctype, name, "read")
	_assert_document_permission(doctype, name, "print")
	doc = frappe.get_doc(doctype, name)
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Only submitted sales documents can be printed as direct receipts."))

	return {
		"schema_version": 1,
		"document_type": "receipt",
		"document_key": definition["key"],
		"doctype": doctype,
		"name": doc.name,
		"company": _text(doc.get("company")),
		"branch": _branch(doc),
		"currency": _text(doc.get("currency")) or "NGN",
		"blocks": _receipt_blocks(doc, definition),
		"metadata": {
			"source_doctype": doctype,
			"source_name": doc.name,
			"docstatus": cint(doc.docstatus),
		},
	}
