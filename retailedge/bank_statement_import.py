from __future__ import annotations

import frappe
from frappe import _


@frappe.whitelist(methods=["POST"])
def create_bank_statement_import(company: str, bank_account: str) -> dict:
	"""Create the native ERPNext Bank Statement Import in a validated banking context.

	RetailEdge owns only the context validation and draft creation. ERPNext remains the
	authority for file parsing, preview, validation, and Bank Transaction import.
	"""
	company = (company or "").strip()
	bank_account = (bank_account or "").strip()
	if not company or not bank_account:
		frappe.throw(_("Company and Bank Account are required."))

	frappe.has_permission("Bank Statement Import", ptype="create", throw=True)
	frappe.has_permission("Bank Transaction", ptype="import", throw=True)

	account = frappe.get_doc("Bank Account", bank_account)
	account.check_permission("read")
	if account.company != company:
		frappe.throw(
			_("Bank Account {0} does not belong to Company {1}.").format(bank_account, company),
			frappe.ValidationError,
		)
	if not account.bank:
		frappe.throw(_("Bank Account {0} is not linked to a Bank.").format(bank_account))

	doc = frappe.new_doc("Bank Statement Import")
	doc.company = company
	doc.bank_account = bank_account
	doc.bank = account.bank
	doc.reference_doctype = "Bank Transaction"
	doc.import_type = "Insert New Records"
	doc.submit_after_import = 1
	doc.mute_emails = 1
	doc.insert()

	return {
		"name": doc.name,
		"company": doc.company,
		"bank_account": doc.bank_account,
		"bank": doc.bank,
		"status": doc.status,
	}
