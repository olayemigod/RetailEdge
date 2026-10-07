from retailedge.print_format_governance import _govern_receipt_html
from retailedge.professional_print_formats import _RECEIPT_HTML


def test_governed_receipt_html_uses_canonical_receipt_policy():
	governed = _govern_receipt_html(_RECEIPT_HTML)

	assert '{% set receipt = output.get("receipt") or {} %}' in governed
	assert 'receipt.get("show_status")' in governed
	assert 'receipt.get("status_label")' in governed
	assert 'receipt.get("show_payment_method")' in governed
	assert 'receipt.get("payment_method_label")' in governed
	assert 'receipt.get("show_amount_in_words")' in governed
	assert 'receipt.get("amount_in_words_label")' in governed
	assert 'receipt.get("show_footer_separator")' in governed
	assert 'receipt.get("show_footer")' in governed
	assert '{{ receipt.get("footer_message") }}' in governed

	# Payment method is descriptive metadata, not a second money subtotal.
	assert 'payment.get_formatted("amount", doc)' not in governed
	# The merchant footer is no longer hard-coded into the installed template.
	assert '<div class="receipt-footer">Thank you for your business.</div>' not in governed


def test_receipt_governance_preserves_branch_and_net_item_contracts():
	governed = _govern_receipt_html(_RECEIPT_HTML)

	assert "output.show_branch and output.branch" in governed
	assert 'row.get_formatted("net_rate", doc)' in governed
	assert 'row.get_formatted("net_amount", doc)' in governed


def test_receipt_governance_is_idempotent():
	governed = _govern_receipt_html(_RECEIPT_HTML)
	assert _govern_receipt_html(governed) == governed
