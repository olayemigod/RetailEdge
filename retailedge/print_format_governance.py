from __future__ import annotations

from typing import Any

from retailedge import professional_print_formats as managed_formats

_DOCUMENT_DATE_ROW = (
	'{% if document_date %}<div><span>Date</span><strong>{{ frappe.utils.formatdate(document_date) }}</strong></div>{% endif %}'
)
_DOCUMENT_BRANCH_ROW = (
	'{% if output.show_branch and output.branch %}<div><span>Branch</span><strong>{{ output.branch }}</strong></div>{% endif %}'
)
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
	if _RECEIPT_BRANCH_ROW not in result and _RECEIPT_CASHIER_ROW in result:
		result = result.replace(
			_RECEIPT_CASHIER_ROW,
			f"{_RECEIPT_CASHIER_ROW}\n\t\t{_RECEIPT_BRANCH_ROW}",
			1,
		)
	result = result.replace(_RECEIPT_RATE, _RECEIPT_NET_RATE)
	result = result.replace(_RECEIPT_AMOUNT, _RECEIPT_NET_AMOUNT)
	return result


def sync_governed_pedge_print_formats() -> dict[str, Any]:
	"""Synchronise managed PEdge formats with shared print-output governance.

	This is presentation-only. It never changes submitted ERPNext documents. Branch
	visibility comes from the exact RetailEdge Branch Profile and is opt-in per Branch.
	The managed receipt templates also use net item values so document receipts and
	direct thermal receipts present discounts consistently.
	"""
	managed_formats._DOCUMENT_HTML = _govern_document_html(managed_formats._DOCUMENT_HTML)
	managed_formats._RECEIPT_HTML = _govern_receipt_html(managed_formats._RECEIPT_HTML)
	return managed_formats.ensure_retailedge_professional_print_formats()
