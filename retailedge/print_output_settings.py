from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

BRANCH_PRINT_VISIBILITY_FIELD = "show_branch_on_printed_documents"


def ensure_print_output_custom_fields() -> None:
	"""Install the per-Branch print visibility policy idempotently.

	The setting belongs to RetailEdge Branch Profile because merchants may want one
	Branch named on customer documents while another Branch stays hidden. Existing
	accounting documents are never changed; the policy affects presentation only.
	"""
	if not frappe.db.exists("DocType", "RetailEdge Branch Profile"):
		return

	create_custom_fields(
		{
			"RetailEdge Branch Profile": [
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
				},
			]
		},
		update=True,
	)
