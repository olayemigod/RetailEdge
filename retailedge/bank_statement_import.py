from __future__ import annotations

import frappe
from frappe import _

from retailedge.bank_account_policy import resolve_retailedge_bank_account


TEMPLATE_DOCTYPE = "RetailEdge Statement Mapping Template"
NATIVE_TEMPLATE_MODE = "Separate Debit/Credit Columns"



def _bank_account_context(company: str, bank_account: str, branch: str = ""):
	company = str(company or "").strip()
	bank_account = str(bank_account or "").strip()
	branch = str(branch or "").strip()
	if not company or not bank_account:
		frappe.throw(_("Company and Bank Account are required."))

	resolved = resolve_retailedge_bank_account(
		company=company,
		branch=branch,
		bank_account=bank_account,
		strict_branch_scope=True,
	)
	account = frappe.get_doc("Bank Account", resolved.get("bank_account") or bank_account)
	account.check_permission("read")
	if not str(account.bank or "").strip():
		frappe.throw(_("Bank Account {0} is not linked to a Bank.").format(bank_account))
	return account


def _template_value(template, fieldname: str) -> str:
	if isinstance(template, dict):
		return str(template.get(fieldname) or "").strip()
	return str(getattr(template, fieldname, "") or "").strip()


def _native_template_mapping(template) -> dict[str, str]:
	mode = _template_value(template, "debit_credit_mode") or NATIVE_TEMPLATE_MODE
	if mode != NATIVE_TEMPLATE_MODE:
		frappe.throw(
			_(
				"This mapping template uses an amount mode that ERPNext Bank Statement Import cannot apply safely. "
				"Use a Separate Debit/Credit Columns template."
			)
		)

	source_to_target = [
		(_template_value(template, "date_column"), "date"),
		(_template_value(template, "reference_column"), "reference_number"),
		(_template_value(template, "narration_column"), "description"),
		(_template_value(template, "debit_column"), "withdrawal"),
		(_template_value(template, "credit_column"), "deposit"),
		(_template_value(template, "currency_column"), "currency"),
	]
	if not source_to_target[0][0]:
		frappe.throw(_("Bank statement mapping template requires a Date Column."))
	if not source_to_target[3][0] and not source_to_target[4][0]:
		frappe.throw(_("Bank statement mapping template requires a Debit Column, Credit Column, or both."))

	mapping: dict[str, str] = {}
	for source, target in source_to_target:
		if not source:
			continue
		if source in mapping and mapping[source] != target:
			frappe.throw(
				_("Statement column {0} is mapped to more than one Bank Transaction field.").format(source)
			)
		mapping[source] = target
	return mapping


def _assert_template_context(template, *, company: str, bank: str) -> None:
	template_company = _template_value(template, "company")
	provider = _template_value(template, "bank_or_provider_name")
	if template_company and template_company != company:
		frappe.throw(_("The selected Import Template belongs to another Company."))
	if provider and provider.casefold() != str(bank or "").strip().casefold():
		frappe.throw(_("The selected Import Template is configured for another Bank."))
	if _template_value(template, "statement_type") != "Bank Transfer":
		frappe.throw(_("Only Bank Transfer mapping templates can be used for Bank Statement Import."))
	if not int(getattr(template, "enabled", 0) or 0):
		frappe.throw(_("The selected Import Template is disabled."))


@frappe.whitelist()
def get_bank_statement_template_options(
	company: str,
	bank_account: str,
	txt: str = "",
	branch: str = "",
) -> dict:
	"""Return enabled reusable mappings valid for the selected Company/Bank."""
	account = _bank_account_context(company, bank_account, branch)
	frappe.has_permission(TEMPLATE_DOCTYPE, ptype="read", throw=True)
	filters = {"enabled": 1, "statement_type": "Bank Transfer"}
	txt = str(txt or "").strip()
	if txt:
		filters["template_name"] = ["like", f"%{txt}%"]

	rows = frappe.get_list(
		TEMPLATE_DOCTYPE,
		fields=[
			"name",
			"template_name",
			"company",
			"bank_or_provider_name",
			"debit_credit_mode",
			"date_column",
			"debit_column",
			"credit_column",
			"modified",
		],
		filters=filters,
		order_by="modified desc",
		limit_page_length=50,
	)
	options = []
	for row in rows:
		row_company = str(row.get("company") or "").strip()
		provider = str(row.get("bank_or_provider_name") or "").strip()
		mode = str(row.get("debit_credit_mode") or "").strip() or NATIVE_TEMPLATE_MODE
		if row_company and row_company != company:
			continue
		if provider and provider.casefold() != str(account.bank or "").strip().casefold():
			continue
		if mode != NATIVE_TEMPLATE_MODE:
			continue
		if not str(row.get("date_column") or "").strip():
			continue
		if not (str(row.get("debit_column") or "").strip() or str(row.get("credit_column") or "").strip()):
			continue
		options.append(
			{
				"value": row.get("name"),
				"label": row.get("template_name") or row.get("name"),
				"description": _("Reusable mapping for {0}").format(provider or account.bank),
			}
		)
		if len(options) >= 20:
			break

	return {
		"options": options,
		"can_create": bool(frappe.has_permission(TEMPLATE_DOCTYPE, ptype="create")),
		"bank": account.bank,
	}


@frappe.whitelist(methods=["POST"])
def create_bank_statement_template(
	company: str,
	bank_account: str,
	template_name: str,
	date_column: str,
	debit_column: str = "",
	credit_column: str = "",
	reference_column: str = "",
	narration_column: str = "",
	currency_column: str = "",
	branch: str = "",
) -> dict:
	"""Create one bounded reusable bank-statement mapping without opening native Desk."""
	account = _bank_account_context(company, bank_account, branch)
	frappe.has_permission(TEMPLATE_DOCTYPE, ptype="create", throw=True)
	template_name = str(template_name or "").strip()
	if not template_name:
		frappe.throw(_("Template Name is required."))

	values = {
		"date_column": str(date_column or "").strip(),
		"debit_column": str(debit_column or "").strip(),
		"credit_column": str(credit_column or "").strip(),
		"reference_column": str(reference_column or "").strip(),
		"narration_column": str(narration_column or "").strip(),
		"currency_column": str(currency_column or "").strip(),
		"debit_credit_mode": NATIVE_TEMPLATE_MODE,
	}
	_native_template_mapping(values)

	doc = frappe.new_doc(TEMPLATE_DOCTYPE)
	doc.template_name = template_name
	doc.enabled = 1
	doc.company = company
	doc.statement_type = "Bank Transfer"
	doc.payment_category = "Bank Transfer"
	doc.bank_or_provider_name = account.bank
	doc.date_column = values["date_column"]
	doc.debit_column = values["debit_column"]
	doc.credit_column = values["credit_column"]
	doc.reference_column = values["reference_column"]
	doc.narration_column = values["narration_column"]
	doc.currency_column = values["currency_column"]
	doc.debit_credit_mode = NATIVE_TEMPLATE_MODE
	doc.insert()

	return {
		"name": doc.name,
		"label": doc.template_name,
		"company": doc.company,
		"bank": doc.bank_or_provider_name,
	}


@frappe.whitelist(methods=["POST"])
def apply_bank_statement_template(
	data_import: str,
	template_name: str,
	branch: str = "",
) -> dict:
	"""Apply a reusable RetailEdge mapping to an existing native ERPNext import draft."""
	data_import = str(data_import or "").strip()
	template_name = str(template_name or "").strip()
	if not data_import or not template_name:
		frappe.throw(_("Bank Statement Import and Import Template are required."))

	doc = frappe.get_doc("Bank Statement Import", data_import)
	doc.check_permission("write")
	if str(doc.reference_doctype or "") != "Bank Transaction":
		frappe.throw(_("Only Bank Transaction imports can use this mapping template."))
	account = _bank_account_context(
		str(doc.company or ""),
		str(doc.bank_account or ""),
		branch,
	)

	template = frappe.get_doc(TEMPLATE_DOCTYPE, template_name)
	template.check_permission("read")
	_assert_template_context(template, company=str(doc.company or ""), bank=str(account.bank or ""))
	mapping = _native_template_mapping(template)

	doc.template_options = frappe.as_json({"column_to_field_map": mapping})
	doc.save()
	return {
		"data_import": doc.name,
		"template_name": template.name,
		"column_to_field_map": mapping,
		"source_of_truth": "ERPNext Bank Statement Import",
	}


@frappe.whitelist(methods=["POST"])
def create_bank_statement_import(company: str, bank_account: str, branch: str = "") -> dict:
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

	account = _bank_account_context(company, bank_account, branch)

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
