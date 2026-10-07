from __future__ import annotations

from typing import Any

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint

BRANCH_PRINT_VISIBILITY_FIELD = "show_branch_on_printed_documents"
RECEIPT_PRESENTATION_SECTION = "receipt_presentation_section"
RECEIPT_PRESENTATION_DEFAULTS: dict[str, Any] = {
	"show_status": 1,
	"status_label": "Status",
	"show_payment_method": 1,
	"payment_method_label": "Payment Method",
	"show_amount_in_words": 1,
	"amount_in_words_label": "Amount in Words",
	"show_footer_separator": 1,
	"show_footer": 1,
	"footer_message": "Thank you for your business.",
}
RECEIPT_SETTING_FIELDS = {
	"show_status": "show_receipt_status",
	"status_label": "receipt_status_label",
	"show_payment_method": "show_receipt_payment_method",
	"payment_method_label": "receipt_payment_method_label",
	"show_amount_in_words": "show_receipt_amount_in_words",
	"amount_in_words_label": "receipt_amount_in_words_label",
	"show_footer_separator": "show_receipt_footer_separator",
	"show_footer": "show_receipt_footer",
	"footer_message": "receipt_footer_message",
}


def _receipt_settings_custom_fields() -> list[dict[str, Any]]:
	return [
		{
			"fieldname": RECEIPT_PRESENTATION_SECTION,
			"label": "Receipt Presentation",
			"fieldtype": "Section Break",
			"insert_after": "enable_sales_payment_audit",
		},
		{
			"fieldname": "show_receipt_status",
			"label": "Show Payment Status on Receipts",
			"fieldtype": "Check",
			"insert_after": RECEIPT_PRESENTATION_SECTION,
			"default": "1",
			"description": "Show the transaction's authoritative status on customer receipts.",
		},
		{
			"fieldname": "receipt_status_label",
			"label": "Receipt Status Label",
			"fieldtype": "Data",
			"insert_after": "show_receipt_status",
			"default": "Status",
			"depends_on": "eval:doc.show_receipt_status",
			"description": "Customer-facing label only. The status value still comes from the submitted transaction.",
		},
		{
			"fieldname": "show_receipt_payment_method",
			"label": "Show Payment Method on Receipts",
			"fieldtype": "Check",
			"insert_after": "receipt_status_label",
			"default": "1",
			"description": "Show the payment method recorded on the transaction.",
		},
		{
			"fieldname": "receipt_payment_method_label",
			"label": "Payment Method Label",
			"fieldtype": "Data",
			"insert_after": "show_receipt_payment_method",
			"default": "Payment Method",
			"depends_on": "eval:doc.show_receipt_payment_method",
			"description": "Customer-facing label only. Payment methods remain transaction-derived.",
		},
		{
			"fieldname": "show_receipt_amount_in_words",
			"label": "Show Amount in Words on Receipts",
			"fieldtype": "Check",
			"insert_after": "receipt_payment_method_label",
			"default": "1",
			"description": "Show the submitted transaction's amount-in-words value.",
		},
		{
			"fieldname": "receipt_amount_in_words_label",
			"label": "Amount in Words Label",
			"fieldtype": "Data",
			"insert_after": "show_receipt_amount_in_words",
			"default": "Amount in Words",
			"depends_on": "eval:doc.show_receipt_amount_in_words",
			"description": "Customer-facing label only. The amount remains derived from the submitted transaction.",
		},
		{
			"fieldname": "show_receipt_footer_separator",
			"label": "Show Receipt Footer Separator",
			"fieldtype": "Check",
			"insert_after": "receipt_amount_in_words_label",
			"default": "1",
			"description": "Show a separator immediately before the receipt footer message.",
		},
		{
			"fieldname": "show_receipt_footer",
			"label": "Show Receipt Footer",
			"fieldtype": "Check",
			"insert_after": "show_receipt_footer_separator",
			"default": "1",
			"description": "Show the configured customer-facing footer message on receipts.",
		},
		{
			"fieldname": "receipt_footer_message",
			"label": "Receipt Footer Message",
			"fieldtype": "Small Text",
			"insert_after": "show_receipt_footer",
			"default": "Thank you for your business.",
			"depends_on": "eval:doc.show_receipt_footer",
			"description": "Merchant-controlled receipt footer. Leave blank to print no footer message.",
		},
	]


def ensure_print_output_custom_fields() -> None:
	"""Install print-presentation policy fields idempotently.

	Branch visibility is Branch-specific. Receipt wording is merchant-wide business
	content. Neither policy mutates submitted accounting documents or printer device
	configuration.
	"""
	custom_fields: dict[str, list[dict[str, Any]]] = {}
	if frappe.db.exists("DocType", "RetailEdge Branch Profile"):
		custom_fields["RetailEdge Branch Profile"] = [
			{
				"fieldname": BRANCH_PRINT_VISIBILITY_FIELD,
				"label": "Show Branch on Printed Documents",
				"fieldtype": "Check",
				"insert_after": "enable_transaction_branch_attribution",
				"default": "0",
				"description": (
					"Show this Branch name on PEdge invoices, receipts and direct thermal receipts. "
					"Enable it only for Branches the merchant wants customer-facing."
				),
			}
		]
	if frappe.db.exists("DocType", "RetailEdge Settings"):
		custom_fields["RetailEdge Settings"] = _receipt_settings_custom_fields()
	if custom_fields:
		create_custom_fields(custom_fields, update=True)


def get_receipt_presentation_settings() -> dict[str, Any]:
	"""Return the canonical merchant receipt-presentation policy.

	Labels and visibility are configurable; transaction status, payment methods and
	amounts are not. Missing schema safely falls back to production defaults during
	upgrade/migration boundaries.
	"""
	result = dict(RECEIPT_PRESENTATION_DEFAULTS)
	if not frappe.db.exists("DocType", "RetailEdge Settings"):
		return result
	try:
		doc = frappe.get_single("RetailEdge Settings")
	except Exception:
		return result

	check_keys = {
		"show_status",
		"show_payment_method",
		"show_amount_in_words",
		"show_footer_separator",
		"show_footer",
	}
	label_keys = {"status_label", "payment_method_label", "amount_in_words_label"}
	for key, fieldname in RECEIPT_SETTING_FIELDS.items():
		if not doc.meta.has_field(fieldname):
			continue
		value = doc.get(fieldname)
		if key in check_keys:
			result[key] = 1 if cint(value) else 0
		elif key in label_keys:
			result[key] = str(value or "").strip() or str(RECEIPT_PRESENTATION_DEFAULTS[key])
		elif key == "footer_message":
			# Blank is intentional: merchants may explicitly choose no footer text.
			result[key] = str(value or "").strip()
	return result
