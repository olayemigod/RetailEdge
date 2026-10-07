from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, formatdate

from retailedge.branch_context import BRANCH_FIELD_CANDIDATES
from retailedge.document_output import _assert_document_permission, get_output_document_definition
from retailedge.print_output_context import (
	get_business_document_qr_payload,
	get_business_print_context,
)
from retailedge.professional_print_formats import RECEIPT_PRINT_FORMATS

SUPPORTED_THERMAL_RECEIPT_DOCTYPES = {"Sales Invoice", "POS Invoice"}
PAPER_CHARACTERS = {58: 32, 80: 48}
ITEM_COLUMN_WIDTHS = {
	58: (10, 3, 9, 10),
	80: (21, 5, 10, 12),
}
META_COLUMN_WIDTHS = {
	58: (12, 20),
	80: (14, 34),
}


def _text(value: Any) -> str:
	return str(value or "").strip()


def _money(value: Any, currency: str) -> str:
	return f"{currency} {flt(value):,.2f}".strip()


def _compact_amount(value: Any) -> str:
	amount = flt(value)
	if amount.is_integer():
		return f"{amount:,.0f}"
	return f"{amount:,.2f}"


def _quantity(value: Any) -> str:
	qty = flt(value)
	return f"{qty:,.0f}" if qty.is_integer() else f"{qty:,.3f}".rstrip("0").rstrip(".")


def _branch(doc) -> str:
	fieldnames = ("retailedge_branch", *BRANCH_FIELD_CANDIDATES)
	seen: set[str] = set()
	for fieldname in fieldnames:
		if not fieldname or fieldname in seen:
			continue
		seen.add(fieldname)
		if doc.meta.has_field(fieldname):
			value = _text(doc.get(fieldname))
			if value:
				return value
	return ""


def _item_label(row) -> str:
	return _text(row.get("item_name") or row.get("item_code") or row.get("description")) or _("Item")


def _template_family(doctype: str) -> str:
	return "PEdge POS Receipt" if doctype == "POS Invoice" else "PEdge Sales Receipt"


def _template_variants(doctype: str) -> dict[str, str]:
	variants: dict[str, str] = {}
	for spec in RECEIPT_PRINT_FORMATS:
		if spec.get("doctype") != doctype:
			continue
		kind = _text(spec.get("kind"))
		if kind == "receipt-58":
			variants["58"] = spec["name"]
		elif kind == "receipt-80":
			variants["80"] = spec["name"]
	return variants


def _wrap_chunks(value: Any, width: int) -> list[str]:
	"""Wrap text into deterministic fixed-width chunks without losing content."""
	text = _text(value)
	if not text:
		return [""]
	width = max(1, cint(width))
	lines: list[str] = []
	for paragraph in text.splitlines() or [text]:
		remaining = paragraph.strip()
		if not remaining:
			lines.append("")
			continue
		while len(remaining) > width:
			split_at = remaining.rfind(" ", 0, width + 1)
			if split_at <= 0:
				split_at = width
			lines.append(remaining[:split_at].rstrip())
			remaining = remaining[split_at:].lstrip()
		lines.append(remaining)
	return lines or [""]


def _label_value_blocks(
	label: str,
	value: Any,
	paper_width: int,
	*,
	bold: bool = False,
) -> list[dict[str, Any]]:
	label_width, value_width = META_COLUMN_WIDTHS.get(paper_width, META_COLUMN_WIDTHS[80])
	value_lines = _wrap_chunks(value, value_width)
	blocks: list[dict[str, Any]] = []
	for index, line in enumerate(value_lines):
		blocks.append(
			{
				"type": "row",
				"columns": [
					{"text": label if index == 0 else "", "width": label_width},
					{"text": line, "width": value_width, "align": "right"},
				],
				"bold": bold,
			}
		)
	return blocks


def _item_table_blocks(doc, paper_width: int) -> list[dict[str, Any]]:
	"""Render the PEdge item list as a horizontal thermal table.

	The table intentionally omits a currency prefix in each item cell so 58 mm paper
	can preserve Product / Qty / Price / Subtotal as true horizontal columns. Currency
	remains explicit in the receipt summary immediately below the table. Row numbering
	is intentionally omitted because it consumes scarce Product width on 58 mm paper
	and can force short item names onto unnecessary continuation lines.
	"""
	product_width, qty_width, price_width, subtotal_width = ITEM_COLUMN_WIDTHS.get(
		paper_width,
		ITEM_COLUMN_WIDTHS[80],
	)
	blocks: list[dict[str, Any]] = [
		{
			"type": "row",
			"columns": [
				{"text": _("Product"), "width": product_width},
				{"text": _("Qty"), "width": qty_width, "align": "right"},
				{"text": _("Price"), "width": price_width, "align": "right"},
				{"text": _("Subtotal"), "width": subtotal_width, "align": "right"},
			],
			"bold": True,
		},
		{"type": "rule"},
	]

	for row in doc.get("items") or []:
		qty = _quantity(row.get("qty"))
		rate = row.get("net_rate") if row.get("net_rate") is not None else row.get("rate")
		amount = row.get("net_amount") if row.get("net_amount") is not None else row.get("amount")
		product_lines = _wrap_chunks(_item_label(row), product_width)
		qty_lines = _wrap_chunks(qty, qty_width)
		price_lines = _wrap_chunks(_compact_amount(rate), price_width)
		subtotal_lines = _wrap_chunks(_compact_amount(amount), subtotal_width)
		line_count = max(len(product_lines), len(qty_lines), len(price_lines), len(subtotal_lines))
		for line_index in range(line_count):
			blocks.append(
				{
					"type": "row",
					"columns": [
						{
							"text": product_lines[line_index] if line_index < len(product_lines) else "",
							"width": product_width,
						},
						{
							"text": qty_lines[line_index] if line_index < len(qty_lines) else "",
							"width": qty_width,
							"align": "right",
						},
						{
							"text": price_lines[line_index] if line_index < len(price_lines) else "",
							"width": price_width,
							"align": "right",
						},
						{
							"text": subtotal_lines[line_index] if line_index < len(subtotal_lines) else "",
							"width": subtotal_width,
							"align": "right",
						},
					],
				}
			)
	return blocks


def _receipt_presentation_blocks(receipt: dict[str, Any], paper_width: int) -> list[dict[str, Any]]:
	"""Render optional merchant-controlled receipt content from canonical context."""
	blocks: list[dict[str, Any]] = []
	status = _text(receipt.get("status"))
	if cint(receipt.get("show_status")) and status:
		blocks.extend(
			_label_value_blocks(
				_text(receipt.get("status_label")) or _("Status"),
				status,
				paper_width,
				bold=True,
			)
		)
	payment_method = _text(receipt.get("payment_method"))
	if cint(receipt.get("show_payment_method")) and payment_method:
		blocks.extend(
			_label_value_blocks(
				_text(receipt.get("payment_method_label")) or _("Payment Method"),
				payment_method,
				paper_width,
			)
		)
	amount_in_words = _text(receipt.get("amount_in_words"))
	if cint(receipt.get("show_amount_in_words")) and amount_in_words:
		label = _text(receipt.get("amount_in_words_label")) or _("Amount in Words")
		blocks.append(
			{
				"type": "text",
				"text": f"{label}: {amount_in_words}",
				"align": "center",
			}
		)
	return blocks


def _receipt_date(doc, definition: dict[str, Any]) -> str:
	date_value = doc.get(definition.get("date_field"))
	if not date_value:
		date_value = doc.get("posting_date") or doc.get("transaction_date")
	if not date_value:
		return ""
	formatted = formatdate(date_value)
	posting_time = _text(doc.get("posting_time")) if doc.meta.has_field("posting_time") else ""
	if posting_time:
		posting_time = posting_time.split(".", 1)[0]
	return f"{formatted} {posting_time}".strip()


def _receipt_blocks(doc, definition: dict[str, Any], paper_width: int) -> list[dict[str, Any]]:
	"""Return a thermal-safe rendition of the canonical PEdge receipt template."""
	currency = _text(doc.get("currency")) or "NGN"
	output = get_business_print_context(doc)
	receipt = dict(output.get("receipt") or {})
	company_label = _text(output.get("display_name") or output.get("company") or doc.get("company"))
	address = _text(output.get("address"))
	phone = _text(output.get("phone"))
	party = _text(doc.get(definition.get("party_field")) or doc.get("customer_name") or doc.get("customer"))
	receipt_date = _receipt_date(doc, definition)
	cashier = _text(doc.get("owner"))
	display_branch = _text(output.get("branch")) if output.get("show_branch") else ""
	blocks: list[dict[str, Any]] = []

	if company_label:
		blocks.append({"type": "text", "text": company_label, "align": "center", "bold": True})
	if address:
		blocks.append({"type": "text", "text": address, "align": "center"})
	if phone:
		blocks.append({"type": "text", "text": phone, "align": "center"})

	receipt_label = _("Return Receipt") if cint(doc.get("is_return")) else _("Receipt")
	blocks.append({"type": "text", "text": receipt_label, "align": "center", "bold": True})
	blocks.extend(_label_value_blocks(_("Invoice No."), doc.name, paper_width, bold=True))
	if receipt_date:
		blocks.extend(_label_value_blocks(_("Date"), receipt_date, paper_width))
	if party:
		blocks.extend(_label_value_blocks(_("Customer"), party, paper_width))
	if cashier:
		blocks.extend(_label_value_blocks(_("Cashier"), cashier, paper_width))
	if display_branch:
		blocks.extend(_label_value_blocks(_("Branch"), display_branch, paper_width))

	blocks.append({"type": "rule"})
	blocks.extend(_item_table_blocks(doc, paper_width))
	blocks.append({"type": "rule"})

	if doc.meta.has_field("total_qty") and doc.get("total_qty") is not None:
		blocks.extend(_label_value_blocks(_("Total Qty"), _quantity(doc.get("total_qty")), paper_width))
	if doc.meta.has_field("net_total"):
		blocks.extend(_label_value_blocks(_("Subtotal"), _money(doc.get("net_total"), currency), paper_width))
	if doc.meta.has_field("discount_amount") and flt(doc.get("discount_amount")):
		blocks.extend(_label_value_blocks(_("Discount"), _money(doc.get("discount_amount"), currency), paper_width))
	if doc.meta.has_field("total_taxes_and_charges") and flt(doc.get("total_taxes_and_charges")):
		blocks.extend(
			_label_value_blocks(
				_("Tax / Charges"),
				_money(doc.get("total_taxes_and_charges"), currency),
				paper_width,
			)
		)

	if doc.meta.has_field("paid_amount") and flt(doc.get("paid_amount")):
		blocks.extend(_label_value_blocks(_("Paid"), _money(doc.get("paid_amount"), currency), paper_width))
	if doc.meta.has_field("change_amount") and flt(doc.get("change_amount")):
		blocks.extend(_label_value_blocks(_("Change"), _money(doc.get("change_amount"), currency), paper_width))

	grand_total = flt(doc.get("grand_total"))
	rounded_total = (
		flt(doc.get("rounded_total"))
		if doc.meta.has_field("rounded_total") and doc.get("rounded_total") is not None
		else 0
	)
	payable_total = rounded_total or grand_total
	blocks.extend(_label_value_blocks(_("Total"), _money(payable_total, currency), paper_width, bold=True))

	if doc.meta.has_field("write_off_amount") and flt(doc.get("write_off_amount")):
		blocks.extend(_label_value_blocks(_("Write Off"), _money(doc.get("write_off_amount"), currency), paper_width))

	outstanding = flt(doc.get("outstanding_amount")) if doc.meta.has_field("outstanding_amount") else 0
	if outstanding > 0:
		blocks.extend(_label_value_blocks(_("Balance Due"), _money(outstanding, currency), paper_width, bold=True))
	elif outstanding < 0:
		blocks.extend(
			_label_value_blocks(
				_("Credit / Refund Due"),
				_money(abs(outstanding), currency),
				paper_width,
				bold=True,
			)
		)

	blocks.extend(_receipt_presentation_blocks(receipt, paper_width))

	qr_payload = get_business_document_qr_payload(doc, company_label)
	if qr_payload:
		blocks.append({"type": "qr", "value": qr_payload, "align": "center", "size": 4})

	footer_message = _text(receipt.get("footer_message"))
	show_footer = bool(cint(receipt.get("show_footer")) and footer_message)
	if show_footer and cint(receipt.get("show_footer_separator")):
		blocks.append({"type": "rule"})
	if show_footer:
		blocks.append({"type": "text", "text": footer_message, "align": "center"})
	return blocks


@frappe.whitelist(methods=["GET"])
def get_thermal_receipt_payload(document: str, name: str) -> dict[str, Any]:
	"""Return the product-owned PEdge receipt contract for EdgeSuite printing."""

	definition = get_output_document_definition(document)
	doctype = definition["doctype"]
	if doctype not in SUPPORTED_THERMAL_RECEIPT_DOCTYPES:
		frappe.throw(_("{0} does not support direct thermal receipt printing.").format(doctype))

	_assert_document_permission(doctype, name, "read")
	_assert_document_permission(doctype, name, "print")
	doc = frappe.get_doc(doctype, name)
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Only submitted sales documents can be printed as direct receipts."))

	variants = _template_variants(doctype)
	blocks_by_paper = {
		str(width): _receipt_blocks(doc, definition, width)
		for width in sorted(PAPER_CHARACTERS)
	}
	return {
		"schema_version": 2,
		"document_type": "receipt",
		"document_key": definition["key"],
		"doctype": doctype,
		"name": doc.name,
		"company": _text(doc.get("company")),
		# Branch remains authoritative for profile resolution even when the merchant
		# chooses not to show it on customer-facing receipts.
		"branch": _branch(doc),
		"currency": _text(doc.get("currency")) or "NGN",
		"template_family": _template_family(doctype),
		"template_variants": variants,
		"blocks": blocks_by_paper["80"],
		"blocks_by_paper": blocks_by_paper,
		"metadata": {
			"source_doctype": doctype,
			"source_name": doc.name,
			"docstatus": cint(doc.docstatus),
			"template_family": _template_family(doctype),
			"template_variants": variants,
		},
	}
