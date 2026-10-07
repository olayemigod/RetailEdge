from unittest.mock import patch

from retailedge.print_format_governance import _govern_receipt_html
from retailedge.print_output_settings import (
	RECEIPT_PRESENTATION_DEFAULTS,
	RECEIPT_SETTING_FIELDS,
	get_receipt_presentation_settings,
)
from retailedge.professional_print_formats import _RECEIPT_HTML


class _ReceiptSettingsMeta:
	def has_field(self, fieldname):
		return fieldname in set(RECEIPT_SETTING_FIELDS.values())


class _ReceiptSettingsDoc(dict):
	meta = _ReceiptSettingsMeta()


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


@patch("retailedge.print_output_settings.frappe.db.exists", return_value=True)
@patch("retailedge.print_output_settings.frappe.get_single")
def test_missing_receipt_setting_values_inherit_production_defaults(mock_get_single, _mock_exists):
	mock_get_single.return_value = _ReceiptSettingsDoc(
		{fieldname: None for fieldname in RECEIPT_SETTING_FIELDS.values()}
	)

	assert get_receipt_presentation_settings() == RECEIPT_PRESENTATION_DEFAULTS


@patch("retailedge.print_output_settings.frappe.db.exists", return_value=True)
@patch("retailedge.print_output_settings.frappe.get_single")
def test_explicit_receipt_setting_values_are_respected(mock_get_single, _mock_exists):
	values = {fieldname: None for fieldname in RECEIPT_SETTING_FIELDS.values()}
	values.update(
		{
			"show_receipt_status": 0,
			"show_receipt_footer": 0,
			"receipt_footer_message": "",
		}
	)
	mock_get_single.return_value = _ReceiptSettingsDoc(values)

	resolved = get_receipt_presentation_settings()
	assert resolved["show_status"] == 0
	assert resolved["show_footer"] == 0
	assert resolved["footer_message"] == ""
	assert resolved["show_payment_method"] == 1
	assert resolved["payment_method_label"] == "Payment Method"
