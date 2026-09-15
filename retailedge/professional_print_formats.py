from __future__ import annotations

from typing import Any

import frappe

# Keep the legacy marker only for recognising formats installed by older releases.
LEGACY_MANAGED_MARKERS = (
	"<!-- retailedge-managed-professional-print-format:v1 -->",
	"<!-- retailedge-managed-print-format:v2 -->",
	"<!-- managed-business-print-format:v3 -->",
)
MANAGED_MARKER = "<!-- managed-business-print-format:v4 -->"

LEGACY_PRINT_FORMAT_ALIASES: tuple[str, ...] = (
	"RetailEdge Professional Quotation",
	"RetailEdge Professional Sales Order",
	"RetailEdge Professional Delivery Note",
	"RetailEdge Professional Sales Invoice",
)

PROFESSIONAL_PRINT_FORMATS: tuple[dict[str, str], ...] = (
	{"name": "Professional Quotation", "doctype": "Quotation", "heading": "Quotation", "kind": "document"},
	{"name": "Professional Sales Order", "doctype": "Sales Order", "heading": "Sales Order", "kind": "document"},
	{"name": "Professional Delivery Note", "doctype": "Delivery Note", "heading": "Delivery Note", "kind": "document"},
	{"name": "Professional Sales Invoice", "doctype": "Sales Invoice", "heading": "Sales Invoice", "kind": "document"},
)

SALES_INVOICE_STYLE_FORMATS: tuple[dict[str, str], ...] = (
	{"name": "Invoice Classic", "doctype": "Sales Invoice", "heading": "Sales Invoice", "kind": "invoice-classic"},
	{"name": "Invoice Modern", "doctype": "Sales Invoice", "heading": "Sales Invoice", "kind": "invoice-modern"},
	{"name": "Invoice Compact", "doctype": "Sales Invoice", "heading": "Sales Invoice", "kind": "invoice-compact"},
	{"name": "Invoice Minimal", "doctype": "Sales Invoice", "heading": "Sales Invoice", "kind": "invoice-minimal"},
	{"name": "Invoice Executive", "doctype": "Sales Invoice", "heading": "Sales Invoice", "kind": "invoice-executive"},
)

RECEIPT_PRINT_FORMATS: tuple[dict[str, str], ...] = (
	{"name": "Sales Receipt 80mm", "doctype": "Sales Invoice", "heading": "Receipt", "kind": "receipt-80"},
	{"name": "Sales Receipt 58mm", "doctype": "Sales Invoice", "heading": "Receipt", "kind": "receipt-58"},
	{"name": "POS Receipt 80mm", "doctype": "POS Invoice", "heading": "Receipt", "kind": "receipt-80"},
	{"name": "POS Receipt 58mm", "doctype": "POS Invoice", "heading": "Receipt", "kind": "receipt-58"},
)

MANAGED_PRINT_FORMATS = PROFESSIONAL_PRINT_FORMATS + SALES_INVOICE_STYLE_FORMATS + RECEIPT_PRINT_FORMATS
PRINT_FORMAT_BY_DOCTYPE = {row["doctype"]: row["name"] for row in PROFESSIONAL_PRINT_FORMATS}

_DOCUMENT_HTML = r"""
<!-- managed-business-print-format:v4 -->
{% set output = get_business_print_context(doc) %}
{% set party = doc.get("customer_name") or doc.get("party_name") or doc.get("customer") or "" %}
{% set document_date = doc.get("transaction_date") or doc.get("posting_date") %}
{% set secondary_date = doc.get("valid_till") or doc.get("delivery_date") or doc.get("due_date") %}
{% set shipping_address = doc.get("shipping_address") or doc.get("shipping_address_display") or "" %}
<div class="pe-document">
	<section class="pe-header">
		<div class="pe-brand">
			{% if output.show_logo and output.logo %}<img class="pe-logo" src="{{ output.logo }}" alt="{{ output.display_name or output.company }}">{% endif %}
			<div class="pe-brand-copy">
				<div class="pe-company">{{ output.display_name or output.company or doc.get("company") or "" }}</div>
				{% if output.address %}<div class="pe-company-address">{{ output.address }}</div>{% endif %}
				{% if output.email or output.phone or output.website %}
				<div class="pe-company-contact">
					{% if output.email %}<span>{{ output.email }}</span>{% endif %}
					{% if output.phone %}<span>{{ output.phone }}</span>{% endif %}
					{% if output.website %}<span>{{ output.website }}</span>{% endif %}
				</div>
				{% endif %}
			</div>
		</div>
		<div class="pe-title-block">
			<h1>__DOCUMENT_HEADING__</h1>
			<div class="pe-document-no"># {{ doc.name }}</div>
			{% if doc.doctype == "Sales Invoice" and doc.get("outstanding_amount") is not none %}
			<div class="pe-balance"><span>Balance Due</span><strong>{{ doc.get_formatted("outstanding_amount") }}</strong></div>
			{% endif %}
			{% if doc.get("status") %}<span class="pe-status">{{ doc.get("status") }}</span>{% endif %}
		</div>
	</section>

	<section class="pe-party-grid">
		<div class="pe-card">
			<div class="pe-label">{% if doc.doctype == "Delivery Note" %}Deliver To{% elif doc.doctype == "Quotation" %}Quote To{% else %}Bill To{% endif %}</div>
			<strong class="pe-party">{{ party }}</strong>
			{% if doc.get("address_display") %}<div>{{ doc.get("address_display") }}</div>{% endif %}
			{% if doc.get("contact_display") %}<div>{{ doc.get("contact_display") }}</div>{% endif %}
			{% if doc.get("contact_mobile") %}<div>{{ doc.get("contact_mobile") }}</div>{% endif %}
			{% if doc.get("contact_email") %}<div>{{ doc.get("contact_email") }}</div>{% endif %}
		</div>
		<div class="pe-card pe-meta">
			{% if document_date %}<div><span>Date</span><strong>{{ frappe.utils.formatdate(document_date) }}</strong></div>{% endif %}
			{% if secondary_date %}<div><span>{% if doc.doctype == "Quotation" %}Valid Till{% elif doc.doctype == "Sales Invoice" %}Due Date{% else %}Delivery Date{% endif %}</span><strong>{{ frappe.utils.formatdate(secondary_date) }}</strong></div>{% endif %}
			{% if doc.get("po_no") %}<div><span>Customer PO</span><strong>{{ doc.get("po_no") }}</strong></div>{% endif %}
			{% if doc.get("shipping_rule") %}<div><span>Shipping Rule</span><strong>{{ doc.get("shipping_rule") }}</strong></div>{% endif %}
		</div>
		{% if shipping_address %}<div class="pe-card pe-wide"><div class="pe-label">Delivery / Shipping Address</div><div>{{ shipping_address }}</div></div>{% endif %}
	</section>

	<table class="pe-items">
		<thead><tr><th>#</th><th>Item & Description</th><th class="num">Qty</th><th class="num">Rate</th><th class="num">Amount</th></tr></thead>
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
			{% if doc.get("remarks") %}<div class="pe-note-block"><span class="pe-label">Notes</span><div>{{ doc.get("remarks") }}</div></div>{% endif %}
			{% if doc.get("incoterm") %}<div><span>Incoterm</span><strong>{{ doc.get("incoterm") }}{% if doc.get("named_place") %} — {{ doc.get("named_place") }}{% endif %}</strong></div>{% endif %}
		</div>
		<div class="pe-totals">
			<div><span>Subtotal</span><strong>{{ doc.get_formatted("net_total") }}</strong></div>
			{% if doc.get("discount_amount") %}<div><span>Discount</span><strong>{{ doc.get_formatted("discount_amount") }}</strong></div>{% endif %}
			{% if doc.get("total_taxes_and_charges") %}<div><span>Taxes & Charges</span><strong>{{ doc.get_formatted("total_taxes_and_charges") }}</strong></div>{% endif %}
			<div class="grand"><span>Total</span><strong>{{ doc.get_formatted("rounded_total") if doc.get("rounded_total") else doc.get_formatted("grand_total") }}</strong></div>
			{% if doc.get("paid_amount") %}<div><span>Payment Made</span><strong>{{ doc.get_formatted("paid_amount") }}</strong></div>{% endif %}
			{% if doc.doctype == "Sales Invoice" and doc.get("outstanding_amount") is not none %}<div class="balance-row"><span>Balance Due</span><strong>{{ doc.get_formatted("outstanding_amount") }}</strong></div>{% endif %}
			{% if doc.get("in_words") %}<div class="words">{{ doc.get("in_words") }}</div>{% endif %}
		</div>
	</section>

	{% if doc.get("payment_schedule") and doc.doctype in ("Quotation", "Sales Order", "Sales Invoice") %}
	<section class="pe-detail"><div class="pe-label">Payment Schedule</div><table><thead><tr><th>Due Date</th><th>Description</th><th class="num">Amount</th></tr></thead><tbody>{% for payment in doc.get("payment_schedule") %}<tr><td>{{ frappe.utils.formatdate(payment.get("due_date")) if payment.get("due_date") else "" }}</td><td>{{ payment.get("description") or payment.get("payment_term") or "" }}</td><td class="num">{{ payment.get_formatted("payment_amount", doc) }}</td></tr>{% endfor %}</tbody></table></section>
	{% endif %}
	{% if doc.get("terms") %}<section class="pe-detail"><div class="pe-label">Terms & Conditions</div><div>{{ doc.get("terms") }}</div></section>{% endif %}

	<section class="pe-bottom">
		<div class="pe-signatures">{% if doc.doctype == "Delivery Note" %}<div>Delivered By</div><div>Received By</div>{% else %}<div>Authorized Signatory</div><div>Customer Acknowledgement</div>{% endif %}</div>
		{% if output.include_qr and output.qr_data_uri %}
		<div class="pe-qr"><img src="{{ output.qr_data_uri }}" alt="Document QR"><span>Document reference</span></div>
		{% endif %}
	</section>
</div>
""".strip()

_DOCUMENT_CSS = r"""
.pe-document{color:#172433;font-size:10pt;line-height:1.4}.pe-header{display:flex;justify-content:space-between;align-items:flex-start;gap:22px;padding-bottom:16px}.pe-brand{display:flex;align-items:flex-start;gap:12px;min-width:0;max-width:60%}.pe-logo{width:44mm;max-width:170px;max-height:34mm;object-fit:contain;object-position:left top}.pe-brand-copy{min-width:0}.pe-company{font-size:11pt;font-weight:800;letter-spacing:.025em;text-transform:uppercase;color:#172433}.pe-company-address,.pe-company-contact{margin-top:3px;color:#59697a;font-size:8.5pt}.pe-company-contact{display:flex;flex-wrap:wrap;gap:4px 10px}.pe-title-block{text-align:right;min-width:190px}.pe-title-block h1{margin:0;font-size:27pt;font-weight:500;letter-spacing:.01em;color:#111}.pe-document-no{margin-top:3px;font-weight:700}.pe-balance{display:grid;gap:2px;margin-top:14px}.pe-balance span{font-size:8pt;color:#6b7280}.pe-balance strong{font-size:12pt}.pe-status{display:inline-block;margin-top:8px;padding:3px 8px;border:1px solid #d7dde4;border-radius:999px;font-size:8pt}.pe-label{font-size:8pt;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#6b7280}.pe-party-grid{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(220px,.75fr);gap:14px;margin:16px 0}.pe-card{padding:2px 0;min-height:64px}.pe-wide{grid-column:1/-1;border-top:1px solid #e5e7eb;padding-top:9px}.pe-party{display:block;margin:4px 0 5px;font-size:11pt}.pe-meta{display:grid;gap:6px;align-content:start}.pe-meta div{display:grid;grid-template-columns:92px 1fr;gap:10px}.pe-meta strong{text-align:right}.pe-items,.pe-detail table{width:100%;border-collapse:collapse}.pe-items th{padding:7px 6px;background:#343434;color:#fff;font-size:8pt;font-weight:600;text-transform:none}.pe-items td,.pe-detail th,.pe-detail td{padding:7px 6px;border-bottom:1px solid #e5e7eb;vertical-align:top}.pe-items th:first-child,.pe-items td:first-child{width:28px}.num{text-align:right}.muted{color:#6b7280;font-size:8pt;margin-top:2px}.pe-summary{display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:28px;margin-top:14px}.pe-notes,.pe-totals{display:grid;gap:7px;align-content:start}.pe-notes>div:not(.pe-note-block),.pe-totals>div{display:flex;justify-content:space-between;gap:16px}.pe-note-block{display:grid;gap:4px;color:#4b5563}.grand{padding-top:8px;margin-top:2px;border-top:1px solid #7b8794;font-size:11pt}.balance-row{padding:8px;background:#f5f6f7;font-weight:700}.words{display:block!important;color:#4b5563;font-size:8pt;font-style:italic}.pe-detail{margin-top:16px;break-inside:avoid}.pe-bottom{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;margin-top:34px}.pe-signatures{display:grid;grid-template-columns:repeat(2,minmax(120px,1fr));gap:44px;flex:1}.pe-signatures div{padding-top:7px;border-top:1px solid #9ca3af;color:#6b7280;font-size:8pt}.pe-qr{display:grid;justify-items:center;gap:2px;color:#6b7280;font-size:7pt}.pe-qr img{width:24mm;height:24mm}.pe-qr span{white-space:nowrap}@media print{.pe-document{font-size:9.3pt}.pe-brand,.pe-card,.pe-detail,.pe-bottom{break-inside:avoid}.pe-logo{max-height:30mm}}
""".strip()

_DOCUMENT_CSS_CLASSIC = _DOCUMENT_CSS + r"""
.pe-header{border-bottom:1px solid #111827}.pe-header h1{font-family:Georgia,serif;font-weight:600}.pe-card{border-radius:0}.pe-items th{background:#fff;border-top:1px solid #111827;border-bottom:1px solid #111827}.grand{border-top:1px double #111827}
""".strip()

_DOCUMENT_CSS_MODERN = _DOCUMENT_CSS + r"""
.pe-header{padding:14px 16px;background:#f3f4f6;border-bottom:0;border-left:5px solid #111827}.pe-header h1{font-size:22pt}.pe-card{border:0;background:#f9fafb}.pe-items th{background:#111827;color:#fff}.grand{background:#f3f4f6;padding:9px 8px}.pe-signatures div{border-top:2px solid #111827}
""".strip()

_DOCUMENT_CSS_COMPACT = _DOCUMENT_CSS + r"""
.pe-document{font-size:9pt;line-height:1.3}.pe-header{padding-bottom:9px}.pe-header h1{font-size:18pt}.pe-party-grid{margin:9px 0;gap:8px}.pe-card{padding:7px 8px;min-height:54px}.pe-items th,.pe-items td,.pe-detail th,.pe-detail td{padding:5px 5px}.pe-summary{margin-top:9px;gap:14px;grid-template-columns:minmax(0,1fr) 240px}.pe-detail{margin-top:11px}.pe-signatures{margin-top:28px}
""".strip()

_DOCUMENT_CSS_MINIMAL = _DOCUMENT_CSS + r"""
.pe-header{border-bottom:1px solid #d1d5db}.pe-status{border:0;padding:0}.pe-card{border:0;padding:4px 0;min-height:0}.pe-party-grid{border-bottom:1px solid #e5e7eb;padding-bottom:12px}.pe-items th{background:transparent;border-bottom:1px solid #111827}.pe-items td{border-bottom:1px solid #f3f4f6}.pe-detail table th{background:transparent}.grand{border-top:1px solid #111827}.pe-signatures div{border-top:1px solid #d1d5db}
""".strip()

_DOCUMENT_CSS_EXECUTIVE = _DOCUMENT_CSS + r"""
.pe-header{background:#111827;color:#fff;padding:16px;border:0}.pe-header h1,.pe-header .pe-company,.pe-header .pe-meta span,.pe-header .pe-meta strong{color:#fff}.pe-status{border-color:#9ca3af}.pe-party-grid{margin-top:18px}.pe-items th{background:#374151;color:#fff}.pe-card{border-color:#d1d5db}.grand{border-top:3px solid #111827}.pe-label{color:#374151}
""".strip()

_DOCUMENT_CSS_BY_KIND = {
	"invoice-classic": _DOCUMENT_CSS_CLASSIC,
	"invoice-modern": _DOCUMENT_CSS_MODERN,
	"invoice-compact": _DOCUMENT_CSS_COMPACT,
	"invoice-minimal": _DOCUMENT_CSS_MINIMAL,
	"invoice-executive": _DOCUMENT_CSS_EXECUTIVE,
}

_RECEIPT_HTML = r"""
<!-- managed-business-print-format:v4 -->
{% set output = get_business_print_context(doc) %}
{% set party = doc.get("customer_name") or doc.get("customer") or "" %}
{% set receipt_date = doc.get("posting_date") or doc.get("transaction_date") %}
<div class="pe-receipt">
	<div class="receipt-brand">
		{% if output.show_logo and output.logo %}<img class="receipt-logo" src="{{ output.logo }}" alt="{{ output.display_name or output.company }}">{% endif %}
		<div class="receipt-company">{{ output.display_name or output.company or doc.get("company") or "" }}</div>
		{% if output.address %}<div class="receipt-address">{{ output.address }}</div>{% endif %}
		{% if output.phone %}<div class="receipt-address">{{ output.phone }}</div>{% endif %}
	</div>
	<div class="receipt-heading">__DOCUMENT_HEADING__</div>
	<div class="receipt-meta-grid">
		<span>Invoice No.</span><strong>{{ doc.name }}</strong>
		{% if receipt_date %}<span>Date</span><strong>{{ frappe.utils.formatdate(receipt_date) }}{% if doc.get("posting_time") %} {{ doc.get("posting_time") }}{% endif %}</strong>{% endif %}
		{% if party %}<span>Customer</span><strong>{{ party }}</strong>{% endif %}
		{% if doc.get("owner") %}<span>Cashier</span><strong>{{ doc.get("owner") }}</strong>{% endif %}
	</div>
	<div class="receipt-rule"></div>
	<table class="receipt-items">
		<thead><tr><th>#</th><th>Product</th><th class="num">Qty</th><th class="num">Unit Price</th><th class="num">Subtotal</th></tr></thead>
		<tbody>
		{% for row in doc.get("items") or [] %}
		<tr>
			<td>{{ row.idx }}</td>
			<td>{{ row.get("item_name") or row.get("item_code") or "" }}</td>
			<td class="num">{{ row.get_formatted("qty", doc) }}</td>
			<td class="num">{{ row.get_formatted("rate", doc) }}</td>
			<td class="num">{{ row.get_formatted("amount", doc) }}</td>
		</tr>
		{% endfor %}
		</tbody>
	</table>
	<div class="receipt-rule"></div>
	<div class="receipt-total"><span>Total Qty</span><strong>{{ doc.get_formatted("total_qty") if doc.get("total_qty") is not none else "" }}</strong></div>
	<div class="receipt-total"><span>Subtotal</span><strong>{{ doc.get_formatted("net_total") }}</strong></div>
	{% if doc.get("discount_amount") %}<div class="receipt-total"><span>Discount</span><strong>{{ doc.get_formatted("discount_amount") }}</strong></div>{% endif %}
	{% if doc.get("total_taxes_and_charges") %}<div class="receipt-total"><span>Tax / Charges</span><strong>{{ doc.get_formatted("total_taxes_and_charges") }}</strong></div>{% endif %}
	{% if doc.get("payments") %}{% for payment in doc.get("payments") %}<div class="receipt-total"><span>{{ payment.get("mode_of_payment") or "Payment" }}</span><strong>{{ payment.get_formatted("amount", doc) }}</strong></div>{% endfor %}{% endif %}
	{% if doc.get("paid_amount") %}<div class="receipt-total"><span>Paid</span><strong>{{ doc.get_formatted("paid_amount") }}</strong></div>{% endif %}
	{% if doc.get("change_amount") %}<div class="receipt-total"><span>Change</span><strong>{{ doc.get_formatted("change_amount") }}</strong></div>{% endif %}
	<div class="receipt-total receipt-grand"><span>Total</span><strong>{{ doc.get_formatted("rounded_total") if doc.get("rounded_total") else doc.get_formatted("grand_total") }}</strong></div>
	{% if doc.get("outstanding_amount") %}<div class="receipt-total"><span>Balance Due</span><strong>{{ doc.get_formatted("outstanding_amount") }}</strong></div>{% endif %}
	{% if doc.get("in_words") %}<div class="receipt-words">{{ doc.get("in_words") }}</div>{% endif %}
	{% if output.include_qr and output.qr_data_uri %}
	<div class="receipt-qr"><img src="{{ output.qr_data_uri }}" alt="Document QR"><span>Document reference</span></div>
	{% endif %}
	<div class="receipt-footer">Thank you for your business.</div>
</div>
""".strip()

_RECEIPT_CSS_80 = r"""
@page{size:80mm auto;margin:2mm}.pe-receipt{width:76mm;margin:0 auto;color:#111;font-family:Arial,sans-serif;font-size:8pt;line-height:1.18}.receipt-brand{text-align:center}.receipt-logo{display:block;max-width:30mm;max-height:16mm;object-fit:contain;margin:0 auto 1mm}.receipt-company{font-size:11pt;font-weight:800;letter-spacing:.02em}.receipt-address{font-size:7pt;margin-top:.4mm}.receipt-heading{text-align:center;font-size:9pt;font-weight:800;text-transform:uppercase;margin:1.4mm 0}.receipt-meta-grid{display:grid;grid-template-columns:21mm 1fr;gap:.6mm 2mm}.receipt-meta-grid strong{text-align:right;font-weight:600}.receipt-rule{border-top:1px dashed #111;margin:1.3mm 0}.receipt-items{width:100%;border-collapse:collapse;table-layout:fixed;font-size:7.4pt}.receipt-items th,.receipt-items td{padding:.7mm .6mm;vertical-align:top;border-bottom:1px dotted #aaa}.receipt-items th{font-weight:700;text-align:left}.receipt-items th:nth-child(1),.receipt-items td:nth-child(1){width:5mm}.receipt-items th:nth-child(2),.receipt-items td:nth-child(2){width:27mm;overflow-wrap:anywhere}.receipt-items th:nth-child(3),.receipt-items td:nth-child(3){width:9mm}.receipt-items th:nth-child(4),.receipt-items td:nth-child(4){width:16mm}.receipt-items th:nth-child(5),.receipt-items td:nth-child(5){width:18mm}.num{text-align:right!important}.receipt-total{display:flex;justify-content:space-between;gap:3mm;margin:.8mm 0}.receipt-total strong{text-align:right}.receipt-grand{font-size:9pt;font-weight:800;border-top:1px solid #111;padding-top:1mm;margin-top:1mm}.receipt-words{text-align:center;font-size:7pt;font-style:italic;margin:1.2mm 2mm}.receipt-qr{display:grid;justify-items:center;gap:.5mm;margin-top:1.7mm;font-size:6.5pt}.receipt-qr img{width:18mm;height:18mm}.receipt-footer{text-align:center;margin-top:1.5mm;font-size:7pt}.print-format{padding:0!important}@media print{html,body{width:80mm;margin:0}.pe-receipt{width:76mm}.receipt-logo{max-height:14mm}.receipt-items tr,.receipt-total,.receipt-qr{break-inside:avoid}}
""".strip()

_RECEIPT_CSS_58 = _RECEIPT_CSS_80.replace("80mm", "58mm").replace("76mm", "54mm").replace("27mm", "18mm").replace("21mm", "16mm").replace("18mm", "13mm").replace("16mm", "12mm").replace("11pt", "9.5pt").replace("9pt", "8pt").replace("8pt", "7.2pt").replace("7.4pt", "6.6pt")


def get_preferred_print_format(doctype: str) -> str:
	return PRINT_FORMAT_BY_DOCTYPE.get(str(doctype or "").strip(), "")


def _format_values(spec: dict[str, str]) -> dict[str, Any]:
	kind = spec.get("kind") or "document"
	is_receipt = kind.startswith("receipt-")
	css = (
		_RECEIPT_CSS_58
		if kind == "receipt-58"
		else _RECEIPT_CSS_80
		if is_receipt
		else _DOCUMENT_CSS_BY_KIND.get(kind, _DOCUMENT_CSS)
	)
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


def is_managed_print_format_html(html: Any) -> bool:
	"""Return whether HTML carries a current or legacy app ownership marker."""
	html = str(html or "")
	return MANAGED_MARKER in html or any(marker in html for marker in LEGACY_MANAGED_MARKERS)


def _is_managed_print_format(doc) -> bool:
	"""Identify formats created by this app using embedded ownership markers only."""
	return is_managed_print_format_html(doc.html)


def ensure_retailedge_professional_print_formats() -> dict[str, int]:
	"""Idempotently install managed formats without replacing user-owned formats."""
	result = {"created": 0, "updated": 0, "skipped": 0}
	if not frappe.db.exists("DocType", "Print Format"):
		return result

	logger = frappe.logger("retailedge")
	for legacy_name in LEGACY_PRINT_FORMAT_ALIASES:
		if not frappe.db.exists("Print Format", legacy_name):
			continue
		legacy_doc = frappe.get_doc("Print Format", legacy_name)
		if not _is_managed_print_format(legacy_doc):
			logger.warning("Skipping non-managed legacy Print Format collision: %s", legacy_name)
			result["skipped"] += 1
			continue
		if not int(legacy_doc.disabled or 0):
			legacy_doc.disabled = 1
			legacy_doc.save()
			result["updated"] += 1

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
		owned = _is_managed_print_format(doc)
		if not owned:
			logger.warning("Skipping non-managed Print Format name collision: %s", name)
			result["skipped"] += 1
			continue
		doc.update(values)
		doc.save()
		result["updated"] += 1

	return result
