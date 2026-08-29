from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from retailedge.bank_statement_import import create_bank_statement_import


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


if __name__ == "__main__":
	unittest.main()
