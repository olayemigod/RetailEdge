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
		qty = flt(row.get("qty"))
		rate = flt(row.get("net_rate") if row.get("net_rate") is not None else row.get("rate"))
		amount = flt(
			row.get("net_amount") if row.get("net_amount") is not None else row.get("amount")
		)
		blocks.append({"type": "text", "text": _item_label(row), "bold": True})
		blocks.append(
			{
				"type": "text",
				"text": _("{0} x {1}").format(
					_quantity(qty),
					_money(rate, currency),
				),
			}
		)
		discount_percentage = flt(row.get("discount_percentage"))
		if discount_percentage:
			blocks.append(
				{
					"type": "text",
					"text": _("Item Discount: {0}%").format(
						f"{discount_percentage:g}"
					),
				}
			)
		# Preserve the complete payable item amount on narrow 58 mm paper.
		blocks.append(
			{
				"type": "text",
				"text": _money(amount, currency),
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
	receipt_label = _("Return Receipt") if cint(doc.get("is_return")) else definition["label"]
	blocks.extend(
		[
			{"type": "text", "text": receipt_label, "align": "center", "bold": True},
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
	if doc.meta.has_field("discount_amount") and flt(doc.get("discount_amount")):
		blocks.append(
			{
				"type": "text",
				"text": _("Additional Discount (included): {0}").format(
					_money(doc.get("discount_amount"), currency)
				),
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
	grand_total = flt(doc.get("grand_total"))
	rounded_total = (
		flt(doc.get("rounded_total"))
		if doc.meta.has_field("rounded_total") and doc.get("rounded_total") is not None
		else 0
	)
	payable_total = rounded_total or grand_total
	if rounded_total and abs(rounded_total - grand_total) > 0.0001:
		blocks.append(
			{
				"type": "text",
				"text": _("Grand Total: {0}").format(_money(grand_total, currency)),
			}
		)
		rounding_adjustment = rounded_total - grand_total
		blocks.append(
			{
				"type": "text",
				"text": _("Rounding: {0}").format(_money(rounding_adjustment, currency)),
			}
		)
	blocks.extend(
		[
			{
				"type": "text",
				"text": _("TOTAL: {0}").format(_money(payable_total, currency)),
				"bold": True,
			},
			{"type": "rule"},
		]
	)

	payment_blocks = _payment_blocks(doc, currency)
	if payment_blocks:
		blocks.append({"type": "text", "text": _("Payment"), "bold": True})
		blocks.extend(payment_blocks)

	if doc.meta.has_field("paid_amount") and flt(doc.get("paid_amount")):
		blocks.append(
			{
				"type": "text",
				"text": _("Tendered: {0}").format(_money(doc.get("paid_amount"), currency)),
			}
		)
	if doc.meta.has_field("change_amount") and flt(doc.get("change_amount")):
		blocks.append(
			{
				"type": "text",
				"text": _("Change: {0}").format(_money(doc.get("change_amount"), currency)),
			}
		)

	if doc.meta.has_field("write_off_amount") and flt(doc.get("write_off_amount")):
		blocks.append(
			{
				"type": "text",
				"text": _("Write Off: {0}").format(_money(doc.get("write_off_amount"), currency)),
			}
		)

	outstanding = (
		flt(doc.get("outstanding_amount")) if doc.meta.has_field("outstanding_amount") else 0
	)
	if outstanding > 0:
		blocks.append(
			{
				"type": "text",
				"text": _("Outstanding: {0}").format(_money(outstanding, currency)),
			}
		)
	elif outstanding < 0:
		blocks.append(
			{
				"type": "text",
				"text": _("Credit / Refund Due: {0}").format(
					_money(abs(outstanding), currency)
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
