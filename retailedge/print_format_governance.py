from __future__ import annotations

from typing import Any

from retailedge import professional_print_formats as managed_formats

_DOCUMENT_DATE_ROW = (
	'{% if document_date %}<div><span>Date</span><strong>{{ frappe.utils.formatdate(document_date) }}</strong></div>{% endif %}'
)
_DOCUMENT_BRANCH_ROW = (
	'{% if output.show_branch and output.branch %}<div><span>Branch</span><strong>{{ output.branch }}</strong></div>{% endif %}'
)
_RECEIPT_OUTPUT_SET = '{% set output = get_business_print_context(doc) %}'
_RECEIPT_PRESENTATION_SET = '{% set receipt = output.get("receipt") or {} %}'
_RECEIPT_CASHIER_ROW = (
	'{% if doc.get("owner") %}<span>Cashier</span><strong>{{ doc.get("owner") }}</strong>{% endif %}'
)
_RECEIPT_BRANCH_ROW = (
	'{% if output.show_branch and output.branch %}<span>Branch</span><strong>{{ output.branch }}</strong>{% endif %}'
)
_RECEIPT_RATE = '{{ row.get_formatted("rate", doc) }}'
_RECEIPT_NET_RATE = (
	'{{ row.get_formatted("net_rate", doc) if row.get("net_rate") is not none else row.get_formatted("rate", doc) }}'
)
_RECEIPT_AMOUNT = '{{ row.get_formatted("amount", doc) }}'
_RECEIPT_NET_AMOUNT = (
	'{{ row.get_formatted("net_amount", doc) if row.get("net_amount") is not none else row.get_formatted("amount", doc) }}'
)
_RECEIPT_PAYMENT_AMOUNT_ROWS = (
	'{% if doc.get("payments") %}{% for payment in doc.get("payments") %}<div class="receipt-total"><span>{{ payment.get("mode_of_payment") or "Payment" }}</span><strong>{{ payment.get_formatted("amount", doc) }}</strong></div>{% endfor %}{% endif %}'
)
_RECEIPT_IN_WORDS_ROW = (
	'{% if doc.get("in_words") %}<div class="receipt-words">{{ doc.get("in_words") }}</div>{% endif %}'
)
_RECEIPT_PRESENTATION_ROWS = '''{% if receipt.get("show_status") and receipt.get("status") %}<div class="receipt-total"><span>{{ receipt.get("status_label") }}</span><strong>{{ receipt.get("status") }}</strong></div>{% endif %}
	{% if receipt.get("show_payment_method") and receipt.get("payment_method") %}<div class="receipt-total"><span>{{ receipt.get("payment_method_label") }}</span><strong>{{ receipt.get("payment_method") }}</strong></div>{% endif %}
	{% if receipt.get("show_amount_in_words") and receipt.get("amount_in_words") %}<div class="receipt-words"><strong>{{ receipt.get("amount_in_words_label") }}:</strong> {{ receipt.get("amount_in_words") }}</div>{% endif %}'''
_RECEIPT_FOOTER_ROW = '<div class="receipt-footer">Thank you for your business.</div>'
_RECEIPT_GOVERNED_FOOTER = '''{% if receipt.get("show_footer") and receipt.get("footer_message") and receipt.get("show_footer_separator") %}<div class="receipt-rule"></div>{% endif %}
	{% if receipt.get("show_footer") and receipt.get("footer_message") %}<div class="receipt-footer">{{ receipt.get("footer_message") }}</div>{% endif %}'''


def _govern_document_html(html: str) -> str:
	result = str(html or "")
	if _DOCUMENT_BRANCH_ROW not in result and _DOCUMENT_DATE_ROW in result:
		result = result.replace(
			_DOCUMENT_DATE_ROW,
			f"{_DOCUMENT_DATE_ROW}\n\t\t\t{_DOCUMENT_BRANCH_ROW}",
			1,
		)
	return result


def _govern_receipt_html(html: str) -> str:
	result = str(html or "")
	if _RECEIPT_PRESENTATION_SET not in result and _RECEIPT_OUTPUT_SET in result:
		result = result.replace(
			_RECEIPT_OUTPUT_SET,
			f"{_RECEIPT_OUTPUT_SET}\n{_RECEIPT_PRESENTATION_SET}",
			1,
		)
	if _RECEIPT_BRANCH_ROW not in result and _RECEIPT_CASHIER_ROW in result:
		result = result.replace(
			_RECEIPT_CASHIER_ROW,
			f"{_RECEIPT_CASHIER_ROW}\n\t\t{_RECEIPT_BRANCH_ROW}",
			1,
		)
	result = result.replace(_RECEIPT_RATE, _RECEIPT_NET_RATE)
	result = result.replace(_RECEIPT_AMOUNT, _RECEIPT_NET_AMOUNT)
	# Payment method is presentation metadata, not another financial subtotal. Paid
	# amount remains separately rendered from ERPNext transaction truth.
	result = result.replace(_RECEIPT_PAYMENT_AMOUNT_ROWS, "")
	if _RECEIPT_PRESENTATION_ROWS not in result and _RECEIPT_IN_WORDS_ROW in result:
		result = result.replace(_RECEIPT_IN_WORDS_ROW, _RECEIPT_PRESENTATION_ROWS, 1)
	if _RECEIPT_GOVERNED_FOOTER not in result and _RECEIPT_FOOTER_ROW in result:
		result = result.replace(_RECEIPT_FOOTER_ROW, _RECEIPT_GOVERNED_FOOTER, 1)
	return result


def sync_governed_pedge_print_formats() -> dict[str, Any]:
	"""Synchronise managed PEdge formats with shared print-output governance.

	This is presentation-only. It never changes submitted ERPNext documents. Branch
	visibility comes from the exact RetailEdge Branch Profile and is opt-in per Branch.
	Receipt status, payment method, amount-in-words visibility/labels, footer separator
	and footer message come from merchant settings while their business values remain
	transaction-derived. Managed receipt item values continue to use ERPNext net values.
	"""
	managed_formats._DOCUMENT_HTML = _govern_document_html(managed_formats._DOCUMENT_HTML)
	managed_formats._RECEIPT_HTML = _govern_receipt_html(managed_formats._RECEIPT_HTML)
	return managed_formats.ensure_retailedge_professional_print_formats()
