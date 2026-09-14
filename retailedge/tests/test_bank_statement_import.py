from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from retailedge.bank_statement_import import (
	apply_bank_statement_template,
	create_bank_statement_import,
	create_bank_statement_template,
	get_bank_statement_template_options,
)


class BankStatementImportSetupTests(unittest.TestCase):
	@patch("retailedge.bank_statement_import.frappe")
	def test_creates_native_import_with_validated_company_and_bank_account(self, mock_frappe):
		account = MagicMock()
		account.company = "RetailEdge Consulting"
		account.bank = "Access Bank"
		mock_frappe.get_doc.return_value = account

		doc = MagicMock()
		doc.name = "Bank Statement Import on 2026-08-26"
		doc.status = "Pending"
		mock_frappe.new_doc.return_value = doc

		result = create_bank_statement_import("RetailEdge Consulting", "Access Bank Ketu - Access Bank")

		mock_frappe.has_permission.assert_any_call("Bank Statement Import", ptype="create", throw=True)
		mock_frappe.has_permission.assert_any_call("Bank Transaction", ptype="import", throw=True)
		account.check_permission.assert_called_once_with("read")
		self.assertEqual(doc.company, "RetailEdge Consulting")
		self.assertEqual(doc.bank_account, "Access Bank Ketu - Access Bank")
		self.assertEqual(doc.bank, "Access Bank")
		self.assertEqual(doc.reference_doctype, "Bank Transaction")
		self.assertEqual(doc.import_type, "Insert New Records")
		self.assertEqual(doc.submit_after_import, 1)
		doc.insert.assert_called_once_with()
		self.assertEqual(result["name"], doc.name)

	@patch("retailedge.bank_statement_import.frappe")
	def test_rejects_bank_account_from_another_company(self, mock_frappe):
		account = SimpleNamespace(company="Another Company", bank="Access Bank")
		account.check_permission = MagicMock()
		mock_frappe.get_doc.return_value = account
		mock_frappe.ValidationError = RuntimeError
		mock_frappe.throw.side_effect = RuntimeError("company mismatch")

		with self.assertRaises(RuntimeError):
			create_bank_statement_import("RetailEdge Consulting", "Other Bank Account")

		mock_frappe.new_doc.assert_not_called()

	@patch("retailedge.bank_statement_import.frappe")
	def test_requires_company_and_bank_account(self, mock_frappe):
		mock_frappe.throw.side_effect = RuntimeError("required")
		with self.assertRaises(RuntimeError):
			create_bank_statement_import("", "")
		mock_frappe.get_doc.assert_not_called()


	@patch("retailedge.bank_statement_import.frappe")
	def test_template_search_is_permission_aware_and_bank_scoped(self, mock_frappe):
		account = MagicMock()
		account.company = "RetailEdge Consulting"
		account.bank = "Access Bank"
		mock_frappe.get_doc.return_value = account
		mock_frappe.has_permission.side_effect = lambda doctype, ptype=None, throw=False: ptype == "create"
		mock_frappe.get_list.return_value = [
			{
				"name": "Access Bank CSV",
				"template_name": "Access Bank CSV",
				"company": "RetailEdge Consulting",
				"bank_or_provider_name": "Access Bank",
				"debit_credit_mode": "Separate Debit/Credit Columns",
				"date_column": "Date",
				"debit_column": "Debit",
				"credit_column": "Credit",
			},
			{
				"name": "Other Bank CSV",
				"template_name": "Other Bank CSV",
				"company": "RetailEdge Consulting",
				"bank_or_provider_name": "Other Bank",
				"debit_credit_mode": "Separate Debit/Credit Columns",
				"date_column": "Date",
				"debit_column": "Debit",
				"credit_column": "Credit",
			},
		]

		result = get_bank_statement_template_options(
			"RetailEdge Consulting",
			"Access Bank Ketu - Access Bank",
			"",
		)

		mock_frappe.get_list.assert_called_once()
		self.assertEqual([row["value"] for row in result["options"]], ["Access Bank CSV"])
		self.assertTrue(result["can_create"])

	@patch("retailedge.bank_statement_import.frappe")
	def test_template_create_is_bounded_to_native_debit_credit_mapping(self, mock_frappe):
		account = MagicMock()
		account.company = "RetailEdge Consulting"
		account.bank = "Access Bank"
		template = MagicMock()
		template.name = "Access Bank CSV"
		template.template_name = "Access Bank CSV"
		mock_frappe.get_doc.return_value = account
		mock_frappe.new_doc.return_value = template

		result = create_bank_statement_template(
			"RetailEdge Consulting",
			"Access Bank Ketu - Access Bank",
			"Access Bank CSV",
			"Transaction Date",
			"Debit",
			"Credit",
			"Reference",
			"Narration",
			"Currency",
		)

		mock_frappe.has_permission.assert_called_with(
			"RetailEdge Statement Mapping Template", ptype="create", throw=True
		)
		self.assertEqual(template.statement_type, "Bank Transfer")
		self.assertEqual(template.debit_credit_mode, "Separate Debit/Credit Columns")
		template.insert.assert_called_once_with()
		self.assertEqual(result["name"], "Access Bank CSV")

	@patch("retailedge.bank_statement_import.frappe")
	def test_apply_template_sets_native_erpnext_template_options_without_second_import_engine(self, mock_frappe):
		import_doc = MagicMock()
		import_doc.name = "Bank Statement Import on 2026-09-14"
		import_doc.company = "RetailEdge Consulting"
		import_doc.bank_account = "Access Bank Ketu - Access Bank"
		import_doc.reference_doctype = "Bank Transaction"
		account = MagicMock()
		account.company = "RetailEdge Consulting"
		account.bank = "Access Bank"
		template = MagicMock()
		template.name = "Access Bank CSV"
		template.company = "RetailEdge Consulting"
		template.bank_or_provider_name = "Access Bank"
		template.statement_type = "Bank Transfer"
		template.enabled = 1
		template.debit_credit_mode = "Separate Debit/Credit Columns"
		template.date_column = "Transaction Date"
		template.reference_column = "Reference"
		template.narration_column = "Narration"
		template.debit_column = "Debit"
		template.credit_column = "Credit"
		template.currency_column = "Currency"
		mock_frappe.get_doc.side_effect = [import_doc, account, template]
		mock_frappe.as_json.return_value = '{"column_to_field_map": {}}'

		result = apply_bank_statement_template(import_doc.name, template.name)

		import_doc.check_permission.assert_called_once_with("write")
		template.check_permission.assert_called_once_with("read")
		self.assertEqual(
			result["column_to_field_map"],
			{
				"Transaction Date": "date",
				"Reference": "reference_number",
				"Narration": "description",
				"Debit": "withdrawal",
				"Credit": "deposit",
				"Currency": "currency",
			},
		)
		import_doc.save.assert_called_once_with()


if __name__ == "__main__":
	unittest.main()
