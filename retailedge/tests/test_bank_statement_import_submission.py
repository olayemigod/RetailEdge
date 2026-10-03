from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from retailedge.bank_transaction_bridge import (
	_create_bank_transaction,
	repair_imported_pending_bank_transactions,
)


class ImportedBankTransactionSubmissionTests(unittest.TestCase):
	@patch(
		"retailedge.bank_transaction_bridge.get_bank_transaction_meta_fields",
		return_value={
			"bank_account": {},
			"date": {},
			"deposit": {},
			"withdrawal": {},
			"currency": {},
			"description": {},
			"reference_number": {},
		},
	)
	@patch("retailedge.bank_transaction_bridge.frappe.has_permission", return_value=True)
	@patch("retailedge.bank_transaction_bridge.frappe.new_doc")
	def test_create_bank_transaction_inserts_and_submits(
		self, mock_new_doc, _has_permission, _mock_meta
	):
		doc = MagicMock()
		doc.name = "ACC-BTN-NEW"
		doc.docstatus = 0
		doc.flags = SimpleNamespace(ignore_permissions=False)
		mock_new_doc.return_value = doc

		name = _create_bank_transaction(
			{
				"bank_account": "Access Bank Ketu - Access Bank",
				"transaction_date": "2026-10-01",
				"deposit": 200000,
				"withdrawal": 0,
				"currency": "NGN",
				"description": "Deposit",
				"reference_number": "REF-1",
			}
		)

		self.assertEqual(name, "ACC-BTN-NEW")
		doc.insert.assert_called_once_with(ignore_permissions=True)
		doc.submit.assert_called_once_with()
		self.assertFalse(doc.flags.ignore_permissions)
		_has_permission.assert_called_once_with("Bank Transaction", ptype="submit")

	@patch(
		"retailedge.bank_transaction_bridge.get_bank_transaction_meta_fields",
		return_value={"bank_account": {}, "date": {}, "deposit": {}, "withdrawal": {}},
	)
	@patch("retailedge.bank_transaction_bridge.frappe.has_permission", return_value=False)
	@patch("retailedge.bank_transaction_bridge.frappe.new_doc")
	def test_create_bank_transaction_requires_submit_permission(
		self, mock_new_doc, _has_permission, _mock_meta
	):
		doc = MagicMock()
		doc.name = "ACC-BTN-DENIED"
		doc.docstatus = 0
		doc.flags = SimpleNamespace(ignore_permissions=False)
		mock_new_doc.return_value = doc

		with self.assertRaises(frappe.PermissionError):
			_create_bank_transaction(
				{
					"bank_account": "Access Bank Ketu - Access Bank",
					"transaction_date": "2026-10-01",
					"deposit": 200000,
					"withdrawal": 0,
				}
			)

		doc.submit.assert_not_called()

	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	@patch("retailedge.bank_transaction_bridge.frappe.db.get_value")
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	@patch("retailedge.bank_transaction_bridge.frappe.db.exists", return_value=True)
	def test_repair_submits_clean_imported_pending_transaction(
		self, _exists, get_all, get_value, get_doc
	):
		get_all.return_value = [
			frappe._dict(
				name="ROW-1",
				bank_transaction="ACC-BTN-2026-00020",
				parent="RE-PSI-1",
			)
		]
		get_value.return_value = frappe._dict(
			name="ACC-BTN-2026-00020",
			docstatus=0,
			status="Pending",
			bank_account="Access Bank Ketu - Access Bank",
			deposit=200000,
			withdrawal=0,
		)
		doc = MagicMock()
		doc.docstatus = 0
		doc.status = "Pending"
		doc.payment_entries = []
		doc.flags = SimpleNamespace(ignore_permissions=False)
		get_doc.return_value = doc

		result = repair_imported_pending_bank_transactions(dry_run=False)

		self.assertEqual(result["repairable"], 1)
		self.assertEqual(result["repaired"], 1)
		doc.submit.assert_called_once_with()
		self.assertTrue(doc.flags.ignore_permissions)

	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	@patch("retailedge.bank_transaction_bridge.frappe.db.get_value")
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	@patch("retailedge.bank_transaction_bridge.frappe.db.exists", return_value=True)
	def test_repair_skips_draft_with_payment_allocations(
		self, _exists, get_all, get_value, get_doc
	):
		get_all.return_value = [
			frappe._dict(name="ROW-1", bank_transaction="ACC-BTN-DRAFT", parent="RE-PSI-1")
		]
		get_value.return_value = frappe._dict(
			name="ACC-BTN-DRAFT",
			docstatus=0,
			status="Pending",
			bank_account="Access Bank Ketu - Access Bank",
			deposit=200000,
			withdrawal=0,
		)
		doc = MagicMock()
		doc.docstatus = 0
		doc.status = "Pending"
		doc.payment_entries = [SimpleNamespace(payment_entry="ACC-PAY-1")]
		doc.flags = SimpleNamespace(ignore_permissions=False)
		get_doc.return_value = doc

		result = repair_imported_pending_bank_transactions(dry_run=False)

		self.assertEqual(result["repaired"], 0)
		self.assertEqual(result["skipped"], 1)
		doc.submit.assert_not_called()

	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	@patch("retailedge.bank_transaction_bridge.frappe.db.get_value")
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	@patch("retailedge.bank_transaction_bridge.frappe.db.exists", return_value=True)
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	@patch("retailedge.bank_transaction_bridge.frappe.db.get_value")
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	@patch("retailedge.bank_transaction_bridge.frappe.db.exists", return_value=True)
	def test_repair_pages_through_all_qualifying_rows(
		self, _exists, get_all, get_value, get_doc
	):
		get_all.side_effect = [
			[frappe._dict(name="ROW-1", bank_transaction="ACC-BTN-1", parent="RE-PSI-1")],
			[frappe._dict(name="ROW-2", bank_transaction="ACC-BTN-2", parent="RE-PSI-1")],
			[],
		]
		get_value.side_effect = [
			frappe._dict(
				name="ACC-BTN-1",
				docstatus=1,
				status="Unreconciled",
				bank_account="Access Bank Ketu - Access Bank",
				deposit=100,
				withdrawal=0,
			),
			frappe._dict(
				name="ACC-BTN-2",
				docstatus=1,
				status="Unreconciled",
				bank_account="Access Bank Ketu - Access Bank",
				deposit=200,
				withdrawal=0,
			),
		]

		result = repair_imported_pending_bank_transactions(dry_run=True, limit=1)

		self.assertEqual(result["checked"], 2)
		self.assertEqual(result["already_submitted"], 2)
		self.assertEqual(get_all.call_count, 3)
		get_doc.assert_not_called()

	def test_repair_is_idempotent_for_already_submitted_transaction(
		self, _exists, get_all, get_value, get_doc
	):
		get_all.return_value = [
			frappe._dict(name="ROW-1", bank_transaction="ACC-BTN-SUBMITTED", parent="RE-PSI-1")
		]
		get_value.return_value = frappe._dict(
			name="ACC-BTN-SUBMITTED",
			docstatus=1,
			status="Unreconciled",
			bank_account="Access Bank Ketu - Access Bank",
			deposit=200000,
			withdrawal=0,
		)

		result = repair_imported_pending_bank_transactions(dry_run=False)

		self.assertEqual(result["already_submitted"], 1)
		self.assertEqual(result["repaired"], 0)
		get_doc.assert_not_called()


if __name__ == "__main__":
	unittest.main()
