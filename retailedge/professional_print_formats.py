from __future__ import annotations

from typing import Any

import frappe

MANAGED_MARKER = "<!-- retailedge-managed-professional-print-format:v1 -->"

PROFESSIONAL_PRINT_FORMATS: tuple[dict[str, str], ...] = (
	{
		"name": "RetailEdge Professional Quotation",
		"doctype": "Quotation",
		"heading": "Quotation",
	},
	{
		"name": "RetailEdge Professional Sales Order",
		"doctype": "Sales Order",
		"heading": "Sales Order",
	},
	{
		"name": "RetailEdge Professional Delivery Note",
		"doctype": "Delivery Note",
		"heading": "Delivery Note",
	},
	{
		"name": "RetailEdge Professional Sales Invoice",
		"doctype": "Sales Invoice",
		"heading": "Sales Invoice",
	},
)

PRINT_FORMAT_BY_DOCTYPE = {row["doctype"]: row["name"] for row in PROFESSIONAL_PRINT_FORMATS}

_BASE_HTML = r"""
<!-- retailedge-managed-professional-print-format:v1 -->
{% set party = doc.get("customer_name") or doc.get("party_name") or doc.get("customer") or "" %}
{% set document_date = doc.get("transaction_date") or doc.get("posting_date") %}
{% set secondary_date = doc.get("valid_till") or doc.get("delivery_date") or doc.get("due_date") %}
{% set shipping_address = doc.get("shipping_address") or doc.get("shipping_address_display") or "" %}
<div class="re-professional-document">
	<section class="re-document-header">
		<div>
			<div class="re-eyebrow">{{ doc.get("company") or "" }}</div>
			<h1>__DOCUMENT_HEADING__</h1>
			{% if doc.get("status") %}<span class="re-status">{{ doc.get("status") }}</span>{% endif %}
		</div>
		<div class="re-document-meta">
			<div><span>Document No.</span><strong>{{ doc.name }}</strong></div>
			{% if document_date %}<div><span>Date</span><strong>{{ frappe.utils.formatdate(document_date) }}</strong></div>{% endif %}
			{% if secondary_date %}
				<div>
					<span>{% if doc.doctype == "Quotation" %}Valid Till{% elif doc.doctype == "Sales Invoice" %}Due Date{% else %}Delivery Date{% endif %}</span>
					<strong>{{ frappe.utils.formatdate(secondary_date) }}</strong>
				</div>
			{% endif %}
		</div>
	</section>

	<section class="re-party-grid">
		<div class="re-party-card">
			<div class="re-section-label">Prepared For</div>
			<strong class="re-party-name">{{ party }}</strong>
			{% if doc.get("address_display") %}<div class="re-address">{{ doc.get("address_display") }}</div>{% endif %}
			{% if doc.get("contact_display") %}<div>{{ doc.get("contact_display") }}</div>{% endif %}
			{% if doc.get("contact_mobile") %}<div>{{ doc.get("contact_mobile") }}</div>{% endif %}
			{% if doc.get("contact_email") %}<div>{{ doc.get("contact_email") }}</div>{% endif %}
		</div>
		{% if shipping_address %}
		<div class="re-party-card">
			<div class="re-section-label">Delivery / Shipping Address</div>
			<div class="re-address">{{ shipping_address }}</div>
		</div>
		{% endif %}
	</section>

	<table class="re-items-table">
		<thead>
			<tr>
				<th class="re-col-index">#</th>
				<th>Item</th>
				<th class="re-col-qty">Qty</th>
				<th class="re-col-money">Rate</th>
				<th class="re-col-money">Amount</th>
			</tr>
		</thead>
		<tbody>
		{% for row in doc.get("items") or [] %}
			<tr>
				<td class="re-col-index">{{ row.idx }}</td>
				<td>
					<strong>{{ row.get("item_name") or row.get("item_code") or "" }}</strong>
					{% if row.get("item_code") and row.get("item_name") and row.get("item_code") != row.get("item_name") %}<div class="re-muted">{{ row.get("item_code") }}</div>{% endif %}
				</td>
				<td class="re-col-qty">{{ row.get_formatted("qty", doc) }}{% if row.get("uom") or row.get("stock_uom") %} {{ row.get("uom") or row.get("stock_uom") }}{% endif %}</td>
				<td class="re-col-money">{{ row.get_formatted("rate", doc) }}</td>
				<td class="re-col-money">{{ row.get_formatted("amount", doc) }}</td>
			</tr>
		{% endfor %}
		</tbody>
	</table>

	<section class="re-summary-grid">
		<div class="re-summary-notes">
			{% if doc.get("po_no") %}<div><span>Customer PO</span><strong>{{ doc.get("po_no") }}</strong></div>{% endif %}
			{% if doc.get("shipping_rule") %}<div><span>Shipping Rule</span><strong>{{ doc.get("shipping_rule") }}</strong></div>{% endif %}
			{% if doc.get("incoterm") %}<div><span>Incoterm</span><strong>{{ doc.get("incoterm") }}{% if doc.get("named_place") %} — {{ doc.get("named_place") }}{% endif %}</strong></div>{% endif %}
		</div>
		<div class="re-totals">
			<div><span>Subtotal</span><strong>{{ doc.get_formatted("net_total") }}</strong></div>
			{% if doc.get("discount_amount") %}<div><span>Discount</span><strong>{{ doc.get_formatted("discount_amount") }}</strong></div>{% endif %}
			{% if doc.get("total_taxes_and_charges") %}<div><span>Taxes & Charges</span><strong>{{ doc.get_formatted("total_taxes_and_charges") }}</strong></div>{% endif %}
			<div class="re-grand-total"><span>Grand Total</span><strong>{{ doc.get_formatted("grand_total") }}</strong></div>
			{% if doc.get("rounded_total") and doc.get("rounded_total") != doc.get("grand_total") %}<div><span>Rounded Total</span><strong>{{ doc.get_formatted("rounded_total") }}</strong></div>{% endif %}
			{% if doc.get("in_words") %}<div class="re-in-words">{{ doc.get("in_words") }}</div>{% endif %}
		</div>
	</section>

	{% if doc.get("taxes") %}
	<section class="re-detail-section">
		<div class="re-section-label">Taxes & Charges</div>
		<table class="re-detail-table">
			<tbody>
			{% for tax in doc.get("taxes") %}
				{% if tax.get("tax_amount_after_discount_amount") or tax.get("tax_amount") %}
				<tr>
					<td>{{ tax.get("description") or tax.get("account_head") or "Charge" }}</td>
					<td class="re-col-money">{{ tax.get_formatted("tax_amount_after_discount_amount", doc) if tax.get("tax_amount_after_discount_amount") else tax.get_formatted("tax_amount", doc) }}</td>
				</tr>
				{% endif %}
			{% endfor %}
			</tbody>
		</table>
	</section>
	{% endif %}

	{% if doc.get("payment_schedule") %}
	<section class="re-detail-section">
		<div class="re-section-label">Payment Schedule</div>
		<table class="re-detail-table">
			<thead><tr><th>Due Date</th><th>Description</th><th class="re-col-money">Amount</th></tr></thead>
			<tbody>
			{% for payment in doc.get("payment_schedule") %}
			<tr>
				<td>{{ frappe.utils.formatdate(payment.get("due_date")) if payment.get("due_date") else "" }}</td>
				<td>{{ payment.get("description") or payment.get("payment_term") or "" }}</td>
				<td class="re-col-money">{{ payment.get_formatted("payment_amount", doc) }}</td>
			</tr>
			{% endfor %}
			</tbody>
		</table>
	</section>
	{% endif %}

	{% if doc.get("terms") %}
	<section class="re-detail-section re-terms">
		<div class="re-section-label">Terms & Conditions</div>
		<div>{{ doc.get("terms") }}</div>
	</section>
	{% endif %}

	<section class="re-signatures">
		{% if doc.doctype == "Delivery Note" %}
		<div><span>Delivered By</span></div><div><span>Received By</span></div>
		{% else %}
		<div><span>Authorized Signatory</span></div><div><span>Customer Acknowledgement</span></div>
		{% endif %}
	</section>
</div>
""".strip()

_BASE_CSS = r"""
.re-professional-document { color: #1f2937; font-size: 10.5pt; line-height: 1.45; }
.re-document-header { display: flex; justify-content: space-between; gap: 20px; padding-bottom: 16px; border-bottom: 2px solid #111827; }
.re-document-header h1 { margin: 3px 0 6px; font-size: 24pt; line-height: 1.1; font-weight: 700; color: #111827; }
.re-eyebrow, .re-section-label { font-size: 8.5pt; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #6b7280; }
.re-status { display: inline-block; padding: 3px 8px; border: 1px solid #d1d5db; border-radius: 999px; font-size: 8.5pt; font-weight: 600; }
.re-document-meta { min-width: 190px; display: grid; gap: 6px; }
.re-document-meta div { display: grid; grid-template-columns: 78px 1fr; gap: 8px; }
.re-document-meta span, .re-summary-notes span, .re-totals span { color: #6b7280; }
.re-document-meta strong { text-align: right; }
.re-party-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 16px 0; }
.re-party-card { border: 1px solid #e5e7eb; border-radius: 7px; padding: 11px 12px; min-height: 78px; }
.re-party-name { display: block; margin: 4px 0 5px; font-size: 12pt; }
.re-address { white-space: normal; }
.re-items-table, .re-detail-table { width: 100%; border-collapse: collapse; }
.re-items-table { margin-top: 4px; }
.re-items-table th { padding: 8px 7px; border-bottom: 1px solid #9ca3af; background: #f3f4f6; font-size: 8.5pt; text-transform: uppercase; letter-spacing: .04em; }
.re-items-table td { padding: 9px 7px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
.re-col-index { width: 34px; text-align: center; }
.re-col-qty { width: 90px; text-align: right; }
.re-col-money { width: 120px; text-align: right; }
.re-muted { margin-top: 2px; color: #6b7280; font-size: 8.5pt; }
.re-summary-grid { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 24px; margin-top: 16px; }
.re-summary-notes { display: grid; align-content: start; gap: 7px; }
.re-summary-notes div, .re-totals div { display: flex; justify-content: space-between; gap: 16px; }
.re-totals { display: grid; gap: 7px; }
.re-grand-total { padding-top: 9px; margin-top: 3px; border-top: 2px solid #111827; font-size: 12pt; }
.re-in-words { display: block !important; padding-top: 5px; color: #4b5563; font-size: 8.5pt; font-style: italic; }
.re-detail-section { margin-top: 18px; break-inside: avoid; }
.re-detail-section > .re-section-label { margin-bottom: 6px; }
.re-detail-table th, .re-detail-table td { padding: 6px 7px; border-bottom: 1px solid #e5e7eb; }
.re-terms { font-size: 9pt; }
.re-signatures { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 48px; margin-top: 42px; page-break-inside: avoid; }
.re-signatures div { padding-top: 8px; border-top: 1px solid #9ca3af; color: #6b7280; font-size: 8.5pt; }
@media print {
	.re-professional-document { font-size: 9.5pt; }
	.re-party-card, .re-detail-section, .re-signatures { break-inside: avoid; }
}
""".strip()


def get_preferred_print_format(doctype: str) -> str:
	return PRINT_FORMAT_BY_DOCTYPE.get(str(doctype or "").strip(), "")


def _format_values(spec: dict[str, str]) -> dict[str, Any]:
	return {
		"print_format_for": "DocType",
		"doc_type": spec["doctype"],
		"module": "RetailEdge",
		"standard": "No",
		"custom_format": 1,
		"disabled": 0,
		"print_format_type": "Jinja",
		"raw_printing": 0,
		"html": _BASE_HTML.replace("__DOCUMENT_HEADING__", spec["heading"]),
		"css": _BASE_CSS,
		"margin_top": 12,
		"margin_bottom": 12,
		"margin_left": 12,
		"margin_right": 12,
		"page_number": "Bottom Right",
	}


def ensure_retailedge_professional_print_formats() -> dict[str, int]:
	"""Idempotently create/update only RetailEdge-owned professional formats.

	An existing exact-name format is updated only when it is already owned by
	RetailEdge (module or managed marker). A third-party/user format that happens
	to use the same name is left untouched and logged.
	"""
	result = {"created": 0, "updated": 0, "skipped": 0}
	if not frappe.db.exists("DocType", "Print Format"):
		return result

	logger = frappe.logger("retailedge")
	for spec in PROFESSIONAL_PRINT_FORMATS:
		if not frappe.db.exists("DocType", spec["doctype"]):
			result["skipped"] += 1
			continue

		values = _format_values(spec)
		name = spec["name"]
		if not frappe.db.exists("Print Format", name):
			doc = frappe.get_doc({"doctype": "Print Format", "name": name, **values})
			doc.insert()
			result["created"] += 1
			continue

		doc = frappe.get_doc("Print Format", name)
		owned = str(doc.module or "") == "RetailEdge" or MANAGED_MARKER in str(doc.html or "")
		if not owned:
			logger.warning("Skipping non-RetailEdge Print Format name collision: %s", name)
			result["skipped"] += 1
			continue
		doc.update(values)
		doc.save()
		result["updated"] += 1

	return result
