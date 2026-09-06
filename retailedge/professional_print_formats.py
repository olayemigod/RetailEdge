from __future__ import annotations

from typing import Any

import frappe

# Internal ownership marker only. It is never rendered to users or customers.
MANAGED_MARKER = "<!-- retailedge-managed-print-format:v2 -->"

PROFESSIONAL_PRINT_FORMATS: tuple[dict[str, str], ...] = (
	{"name": "Professional Quotation", "doctype": "Quotation", "heading": "Quotation", "kind": "document"},
	{"name": "Professional Sales Order", "doctype": "Sales Order", "heading": "Sales Order", "kind": "document"},
	{"name": "Professional Delivery Note", "doctype": "Delivery Note", "heading": "Delivery Note", "kind": "document"},
	{"name": "Professional Sales Invoice", "doctype": "Sales Invoice", "heading": "Sales Invoice", "kind": "document"},
)

RECEIPT_PRINT_FORMATS: tuple[dict[str, str], ...] = (
	{"name": "Sales Receipt 80mm", "doctype": "Sales Invoice", "heading": "Receipt", "kind": "receipt-80"},
	{"name": "Sales Receipt 58mm", "doctype": "Sales Invoice", "heading": "Receipt", "kind": "receipt-58"},
	{"name": "POS Receipt 80mm", "doctype": "POS Invoice", "heading": "Receipt", "kind": "receipt-80"},
	{"name": "POS Receipt 58mm", "doctype": "POS Invoice", "heading": "Receipt", "kind": "receipt-58"},
)

MANAGED_PRINT_FORMATS = PROFESSIONAL_PRINT_FORMATS + RECEIPT_PRINT_FORMATS
PRINT_FORMAT_BY_DOCTYPE = {row["doctype"]: row["name"] for row in PROFESSIONAL_PRINT_FORMATS}

_DOCUMENT_HTML = r"""
<!-- retailedge-managed-print-format:v2 -->
{% set party = doc.get("customer_name") or doc.get("party_name") or doc.get("customer") or "" %}
{% set document_date = doc.get("transaction_date") or doc.get("posting_date") %}
{% set secondary_date = doc.get("valid_till") or doc.get("delivery_date") or doc.get("due_date") %}
{% set shipping_address = doc.get("shipping_address") or doc.get("shipping_address_display") or "" %}
<div class="pe-document">
	<section class="pe-header">
		<div>
			<div class="pe-company">{{ doc.get("company") or "" }}</div>
			<h1>__DOCUMENT_HEADING__</h1>
			{% if doc.get("status") %}<span class="pe-status">{{ doc.get("status") }}</span>{% endif %}
		</div>
		<div class="pe-meta">
			<div><span>Document No.</span><strong>{{ doc.name }}</strong></div>
			{% if document_date %}<div><span>Date</span><strong>{{ frappe.utils.formatdate(document_date) }}</strong></div>{% endif %}
			{% if secondary_date %}<div><span>{% if doc.doctype == "Quotation" %}Valid Till{% elif doc.doctype == "Sales Invoice" %}Due Date{% else %}Delivery Date{% endif %}</span><strong>{{ frappe.utils.formatdate(secondary_date) }}</strong></div>{% endif %}
		</div>
	</section>
	<section class="pe-party-grid">
		<div class="pe-card">
			<div class="pe-label">Prepared For</div>
			<strong class="pe-party">{{ party }}</strong>
			{% if doc.get("address_display") %}<div>{{ doc.get("address_display") }}</div>{% endif %}
			{% if doc.get("contact_display") %}<div>{{ doc.get("contact_display") }}</div>{% endif %}
			{% if doc.get("contact_mobile") %}<div>{{ doc.get("contact_mobile") }}</div>{% endif %}
			{% if doc.get("contact_email") %}<div>{{ doc.get("contact_email") }}</div>{% endif %}
		</div>
		{% if shipping_address %}<div class="pe-card"><div class="pe-label">Delivery / Shipping Address</div><div>{{ shipping_address }}</div></div>{% endif %}
	</section>
	<table class="pe-items">
		<thead><tr><th>#</th><th>Item</th><th class="num">Qty</th><th class="num">Rate</th><th class="num">Amount</th></tr></thead>
		<tbody>
		{% for row in doc.get("items") or [] %}
		<tr>
			<td>{{ row.idx }}</td>
			<td><strong>{{ row.get("item_name") or row.get("item_code") or "" }}</strong>{% if row.get("description") and row.get("description") != row.get("item_name") %}<div class="muted">{{ row.get("description") }}</div>{% endif %}</td>
			<td class="num">{{ row.get_formatted("qty", doc) }}{% if row.get("uom") or row.get("stock_uom") %} {{ row.get("uom") or row.get("stock_uom") }}{% endif %}</td>
			<td class="num">{{ row.get_formatted("rate", doc) }}</td>
			<td class="num">{{ row.get_formatted("amount", doc) }}</td>
		</tr>
		{% endfor %}
		</tbody>
	</table>
	<section class="pe-summary">
		<div class="pe-notes">
			{% if doc.get("po_no") %}<div><span>Customer PO</span><strong>{{ doc.get("po_no") }}</strong></div>{% endif %}
			{% if doc.get("shipping_rule") %}<div><span>Shipping Rule</span><strong>{{ doc.get("shipping_rule") }}</strong></div>{% endif %}
			{% if doc.get("incoterm") %}<div><span>Incoterm</span><strong>{{ doc.get("incoterm") }}{% if doc.get("named_place") %} — {{ doc.get("named_place") }}{% endif %}</strong></div>{% endif %}
		</div>
		<div class="pe-totals">
			<div><span>Subtotal</span><strong>{{ doc.get_formatted("net_total") }}</strong></div>
			{% if doc.get("discount_amount") %}<div><span>Discount</span><strong>{{ doc.get_formatted("discount_amount") }}</strong></div>{% endif %}
			{% if doc.get("total_taxes_and_charges") %}<div><span>Taxes & Charges</span><strong>{{ doc.get_formatted("total_taxes_and_charges") }}</strong></div>{% endif %}
			<div class="grand"><span>Grand Total</span><strong>{{ doc.get_formatted("grand_total") }}</strong></div>
			{% if doc.get("rounded_total") and doc.get("rounded_total") != doc.get("grand_total") %}<div><span>Rounded Total</span><strong>{{ doc.get_formatted("rounded_total") }}</strong></div>{% endif %}
			{% if doc.get("in_words") %}<div class="words">{{ doc.get("in_words") }}</div>{% endif %}
		</div>
	</section>
	{% if doc.get("payment_schedule") %}<section class="pe-detail"><div class="pe-label">Payment Schedule</div><table><thead><tr><th>Due Date</th><th>Description</th><th class="num">Amount</th></tr></thead><tbody>{% for payment in doc.get("payment_schedule") %}<tr><td>{{ frappe.utils.formatdate(payment.get("due_date")) if payment.get("due_date") else "" }}</td><td>{{ payment.get("description") or payment.get("payment_term") or "" }}</td><td class="num">{{ payment.get_formatted("payment_amount", doc) }}</td></tr>{% endfor %}</tbody></table></section>{% endif %}
	{% if doc.get("terms") %}<section class="pe-detail"><div class="pe-label">Terms & Conditions</div><div>{{ doc.get("terms") }}</div></section>{% endif %}
	<section class="pe-signatures">{% if doc.doctype == "Delivery Note" %}<div>Delivered By</div><div>Received By</div>{% else %}<div>Authorized Signatory</div><div>Customer Acknowledgement</div>{% endif %}</section>
</div>
""".strip()

_DOCUMENT_CSS = r"""
.pe-document{color:#1f2937;font-size:10.5pt;line-height:1.45}.pe-header{display:flex;justify-content:space-between;gap:20px;padding-bottom:16px;border-bottom:2px solid #111827}.pe-header h1{margin:3px 0 6px;font-size:24pt;color:#111827}.pe-company,.pe-label{font-size:8.5pt;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#6b7280}.pe-status{display:inline-block;padding:3px 8px;border:1px solid #d1d5db;border-radius:999px;font-size:8.5pt}.pe-meta{min-width:190px;display:grid;gap:6px}.pe-meta div{display:grid;grid-template-columns:78px 1fr;gap:8px}.pe-meta strong{text-align:right}.pe-party-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:16px 0}.pe-card{border:1px solid #e5e7eb;border-radius:7px;padding:11px 12px;min-height:78px}.pe-party{display:block;margin:4px 0 5px;font-size:12pt}.pe-items,.pe-detail table{width:100%;border-collapse:collapse}.pe-items th{padding:8px 7px;border-bottom:1px solid #9ca3af;background:#f3f4f6;font-size:8.5pt;text-transform:uppercase}.pe-items td,.pe-detail th,.pe-detail td{padding:8px 7px;border-bottom:1px solid #e5e7eb;vertical-align:top}.num{text-align:right}.muted{color:#6b7280;font-size:8.5pt}.pe-summary{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:24px;margin-top:16px}.pe-notes,.pe-totals{display:grid;gap:7px;align-content:start}.pe-notes div,.pe-totals div{display:flex;justify-content:space-between;gap:16px}.grand{padding-top:9px;margin-top:3px;border-top:2px solid #111827;font-size:12pt}.words{display:block!important;color:#4b5563;font-size:8.5pt;font-style:italic}.pe-detail{margin-top:18px;break-inside:avoid}.pe-signatures{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:48px;margin-top:42px}.pe-signatures div{padding-top:8px;border-top:1px solid #9ca3af;color:#6b7280;font-size:8.5pt}@media print{.pe-document{font-size:9.5pt}.pe-card,.pe-detail,.pe-signatures{break-inside:avoid}}
""".strip()

_RECEIPT_HTML = r"""
<!-- retailedge-managed-print-format:v2 -->
{% set party = doc.get("customer_name") or doc.get("customer") or "" %}
{% set receipt_date = doc.get("posting_date") or doc.get("transaction_date") %}
<div class="pe-receipt">
	<div class="receipt-company">{{ doc.get("company") or "" }}</div>
	<div class="receipt-heading">__DOCUMENT_HEADING__</div>
	<div class="receipt-meta"><span>No.</span><strong>{{ doc.name }}</strong></div>
	{% if receipt_date %}<div class="receipt-meta"><span>Date</span><strong>{{ frappe.utils.formatdate(receipt_date) }}</strong></div>{% endif %}
	{% if doc.get("posting_time") %}<div class="receipt-meta"><span>Time</span><strong>{{ doc.get("posting_time") }}</strong></div>{% endif %}
	{% if party %}<div class="receipt-meta"><span>Customer</span><strong>{{ party }}</strong></div>{% endif %}
	<div class="receipt-rule"></div>
	{% for row in doc.get("items") or [] %}
	<div class="receipt-item">
		<div class="receipt-item-name">{{ row.get("item_name") or row.get("item_code") or "" }}</div>
		<div class="receipt-item-line"><span>{{ row.get_formatted("qty", doc) }} × {{ row.get_formatted("rate", doc) }}</span><strong>{{ row.get_formatted("amount", doc) }}</strong></div>
	</div>
	{% endfor %}
	<div class="receipt-rule"></div>
	<div class="receipt-total"><span>Subtotal</span><strong>{{ doc.get_formatted("net_total") }}</strong></div>
	{% if doc.get("discount_amount") %}<div class="receipt-total"><span>Discount</span><strong>{{ doc.get_formatted("discount_amount") }}</strong></div>{% endif %}
	{% if doc.get("total_taxes_and_charges") %}<div class="receipt-total"><span>Taxes & Charges</span><strong>{{ doc.get_formatted("total_taxes_and_charges") }}</strong></div>{% endif %}
	<div class="receipt-total receipt-grand"><span>Total</span><strong>{{ doc.get_formatted("rounded_total") if doc.get("rounded_total") else doc.get_formatted("grand_total") }}</strong></div>
	{% if doc.get("payments") %}<div class="receipt-rule"></div>{% for payment in doc.get("payments") %}<div class="receipt-total"><span>{{ payment.get("mode_of_payment") or "Payment" }}</span><strong>{{ payment.get_formatted("amount", doc) }}</strong></div>{% endfor %}{% endif %}
	{% if doc.get("paid_amount") %}<div class="receipt-total"><span>Paid</span><strong>{{ doc.get_formatted("paid_amount") }}</strong></div>{% endif %}
	{% if doc.get("change_amount") %}<div class="receipt-total"><span>Change</span><strong>{{ doc.get_formatted("change_amount") }}</strong></div>{% endif %}
	{% if doc.get("outstanding_amount") %}<div class="receipt-total"><span>Balance Due</span><strong>{{ doc.get_formatted("outstanding_amount") }}</strong></div>{% endif %}
	<div class="receipt-rule"></div>
	<div class="receipt-footer">Thank you for your business.</div>
</div>
""".strip()

_RECEIPT_CSS_80 = r"""
@page{size:80mm auto;margin:3mm}.pe-receipt{width:72mm;margin:0 auto;color:#111;font-family:Arial,sans-serif;font-size:9pt;line-height:1.3}.receipt-company,.receipt-heading{text-align:center;font-weight:700}.receipt-company{font-size:12pt}.receipt-heading{font-size:10pt;text-transform:uppercase;margin:2mm 0}.receipt-meta,.receipt-total,.receipt-item-line{display:flex;justify-content:space-between;gap:4mm}.receipt-meta strong,.receipt-item-line strong,.receipt-total strong{text-align:right}.receipt-rule{border-top:1px dashed #111;margin:2mm 0}.receipt-item{margin:1.6mm 0}.receipt-item-name{font-weight:600}.receipt-grand{font-size:11pt;border-top:1px solid #111;padding-top:1.5mm;margin-top:1.5mm}.receipt-footer{text-align:center;margin-top:3mm}.print-format{padding:0!important}@media print{html,body{width:80mm}.pe-receipt{width:72mm}}
""".strip()

_RECEIPT_CSS_58 = _RECEIPT_CSS_80.replace("80mm", "58mm").replace("72mm", "52mm").replace("9pt", "8pt").replace("12pt", "10pt").replace("11pt", "9pt")


def get_preferred_print_format(doctype: str) -> str:
	return PRINT_FORMAT_BY_DOCTYPE.get(str(doctype or "").strip(), "")


def _format_values(spec: dict[str, str]) -> dict[str, Any]:
	kind = spec.get("kind") or "document"
	is_receipt = kind.startswith("receipt-")
	css = _RECEIPT_CSS_58 if kind == "receipt-58" else _RECEIPT_CSS_80 if is_receipt else _DOCUMENT_CSS
	html = _RECEIPT_HTML if is_receipt else _DOCUMENT_HTML
	return {
		"print_format_for": "DocType",
		"doc_type": spec["doctype"],
		# Internal module identity is intentionally stable and is not customer-facing.
		"module": "RetailEdge",
		"standard": "No",
		"custom_format": 1,
		"disabled": 0,
		"print_format_type": "Jinja",
		"raw_printing": 0,
		"html": html.replace("__DOCUMENT_HEADING__", spec["heading"]),
		"css": css,
		"margin_top": 3 if is_receipt else 12,
		"margin_bottom": 3 if is_receipt else 12,
		"margin_left": 3 if is_receipt else 12,
		"margin_right": 3 if is_receipt else 12,
		"page_number": "Hide" if is_receipt else "Bottom Right",
	}


def ensure_retailedge_professional_print_formats() -> dict[str, int]:
	"""Idempotently install managed formats without replacing user-owned formats."""
	result = {"created": 0, "updated": 0, "skipped": 0}
	if not frappe.db.exists("DocType", "Print Format"):
		return result

	logger = frappe.logger("retailedge")
	for spec in MANAGED_PRINT_FORMATS:
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
			logger.warning("Skipping non-managed Print Format name collision: %s", name)
			result["skipped"] += 1
			continue
		doc.update(values)
		doc.save()
		result["updated"] += 1

	return result
