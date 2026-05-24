from __future__ import annotations

import json
import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from retailedge.bank_transaction_bridge import (
	accept_possible_duplicate_statement_row,
	build_statement_row_fingerprint,
	find_existing_statement_row_duplicate,
	create_or_link_bank_transaction_from_statement_row,
	find_existing_bank_transaction_duplicate,
	get_bank_transaction_meta_fields,
	get_possible_duplicate_statement_rows,
	import_statement_rows_to_bank_transactions,
	is_reliable_statement_reference,
	normalize_statement_reference,
	normalize_statement_row_for_bank_transaction,
	preview_bank_transaction_import,
)


class BankTransactionBridgeTests(unittest.TestCase):
	def _field(self, fieldname, fieldtype="Data", reqd=0, read_only=0, options=None, default=None):
		return SimpleNamespace(
			fieldname=fieldname,
			fieldtype=fieldtype,
			reqd=reqd,
			read_only=read_only,
			options=options,
			default=default,
		)

	def _import_doc(self, **kwargs):
		defaults = {
			"doctype": "RetailEdge Payment Statement Import",
			"name": "RE-PSI-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"payment_category": "Bank Transfer",
		}
		defaults.update(kwargs)
		return SimpleNamespace(**defaults)

	def _row_doc(self, **kwargs):
		defaults = {
			"doctype": "RetailEdge Statement Import Row",
			"name": "ROW-0001",
			"parent": "RE-PSI-0001",
			"transaction_date": "2026-05-22",
			"value_date": "2026-05-22",
			"reference": " trf-001 / 998 ",
			"normalized_reference": None,
			"narration": "Customer transfer",
			"normalized_narration": None,
			"amount": 1000.0,
			"normalized_amount": None,
			"direction": "Credit",
			"transaction_direction": None,
			"credit": 1000.0,
			"debit": 0.0,
			"currency": "NGN",
			"account": "Bank Clearing",
			"normalized_account": None,
			"party": "Customer A",
		}
		defaults.update(kwargs)
		return SimpleNamespace(**defaults)

	@patch("retailedge.bank_transaction_bridge.frappe.get_meta")
	def test_bank_transaction_schema_inspection_works(self, mock_get_meta):
		mock_get_meta.return_value = SimpleNamespace(fields=[self._field("bank_account", "Link"), self._field("date", "Date")])
		meta_fields = get_bank_transaction_meta_fields()
		self.assertIn("bank_account", meta_fields)
		self.assertEqual(meta_fields["date"].fieldtype, "Date")

	def test_reference_normalization_is_stable(self):
		self.assertEqual(
			normalize_statement_reference(reference=" trf-001 / 998 ", narration="Customer transfer"),
			"TRF001998",
		)
		self.assertEqual(normalize_statement_reference(reference="", narration="Customer transfer"), "")

	def test_reliable_reference_helper_distinguishes_generic_values(self):
		self.assertTrue(is_reliable_statement_reference("TRF12345"))
		self.assertFalse(is_reliable_statement_reference(""))
		self.assertFalse(is_reliable_statement_reference("POS"))
		self.assertFalse(is_reliable_statement_reference("0000"))

	def test_statement_row_fingerprint_is_stable(self):
		first = build_statement_row_fingerprint(
			company="Process Edge (Demo)",
			bank_account="Moniepoint - moniepoint",
			transaction_date="2026-05-22",
			amount=1000,
			reference="TRF001",
			direction="Inflow",
		)
		second = build_statement_row_fingerprint(
			company="Process Edge (Demo)",
			bank_account="Moniepoint - moniepoint",
			transaction_date="2026-05-22",
			amount=1000,
			reference="TRF001",
			direction="Inflow",
		)
		self.assertEqual(first, second)

	def test_normalized_credit_row_maps_to_deposit(self):
		normalized = normalize_statement_row_for_bank_transaction(self._row_doc(), import_doc=self._import_doc())
		self.assertEqual(normalized["direction"], "Inflow")
		self.assertEqual(normalized["deposit"], 1000.0)
		self.assertEqual(normalized["withdrawal"], 0.0)
		self.assertFalse(normalized["errors"])

	def test_normalized_debit_row_maps_to_withdrawal(self):
		row = self._row_doc(direction="Debit", credit=0.0, debit=750.0, amount=750.0, narration="Settlement charge")
		normalized = normalize_statement_row_for_bank_transaction(row, import_doc=self._import_doc())
		self.assertEqual(normalized["direction"], "Outflow")
		self.assertEqual(normalized["deposit"], 0.0)
		self.assertEqual(normalized["withdrawal"], 750.0)

	def test_invalid_row_detected_when_required_values_missing(self):
		row = self._row_doc(transaction_date=None, amount=0, credit=0, debit=0, direction="Unknown")
		normalized = normalize_statement_row_for_bank_transaction(row, import_doc=self._import_doc(bank_account=None))
		self.assertGreaterEqual(len(normalized["errors"]), 3)

	@patch("retailedge.bank_transaction_bridge.get_bank_transaction_meta_fields", return_value={"bank_account": {}, "date": {}, "deposit": {}})
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	def test_existing_bank_transaction_duplicate_is_detected(self, mock_get_all, _mock_meta):
		mock_get_all.side_effect = [[
			SimpleNamespace(
				name="ACC-BTN-0001",
				bank_account="Moniepoint - moniepoint",
				date="2026-05-22",
				deposit=1000.0,
				withdrawal=0.0,
				description="Customer transfer",
				reference_number="TRF001998",
				status="Pending",
			)
		], []]
		result = find_existing_bank_transaction_duplicate(
			{
				"bank_account": "Moniepoint - moniepoint",
				"transaction_date": "2026-05-22",
				"amount": 1000.0,
				"direction": "Inflow",
				"normalized_reference": "TRF001998",
				"description": "Customer transfer",
			}
		)
		self.assertTrue(result["is_duplicate"])
		self.assertEqual(result["bank_transaction"], "ACC-BTN-0001")

	@patch("retailedge.bank_transaction_bridge.get_bank_transaction_meta_fields", return_value={"bank_account": {}, "date": {}, "deposit": {}, "reference_number": {}})
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	def test_same_date_amount_different_reliable_reference_is_not_duplicate(self, mock_get_all, _mock_meta):
		mock_get_all.side_effect = [[
			SimpleNamespace(
				name="ACC-BTN-0002",
				bank_account="Moniepoint - moniepoint",
				date="2026-05-22",
				deposit=1000.0,
				withdrawal=0.0,
				description="Another transfer",
				reference_number="TRF999999",
				status="Pending",
			)
		], []]
		result = find_existing_bank_transaction_duplicate(
			{
				"bank_account": "Moniepoint - moniepoint",
				"transaction_date": "2026-05-22",
				"amount": 1000.0,
				"direction": "Inflow",
				"normalized_reference": "TRF001998",
				"reference_number": "TRF001998",
				"description": "Customer transfer",
			}
		)
		self.assertFalse(result["is_duplicate"])

	@patch("retailedge.bank_transaction_bridge.get_bank_transaction_meta_fields", return_value={"bank_account": {}, "date": {}, "deposit": {}, "reference_number": {}})
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	def test_same_date_amount_missing_reference_is_possible_duplicate(self, mock_get_all, _mock_meta):
		mock_get_all.side_effect = [[
			SimpleNamespace(
				name="ACC-BTN-0003",
				bank_account="Moniepoint - moniepoint",
				date="2026-05-22",
				deposit=1000.0,
				withdrawal=0.0,
				description="Customer transfer",
				reference_number="",
				status="Pending",
			)
		], []]
		result = find_existing_bank_transaction_duplicate(
			{
				"bank_account": "Moniepoint - moniepoint",
				"transaction_date": "2026-05-22",
				"amount": 1000.0,
				"direction": "Inflow",
				"normalized_reference": "",
				"reference_number": "",
				"description": "Customer transfer",
			}
		)
		self.assertTrue(result["is_duplicate"])
		self.assertEqual(result["duplicate_type"], "Possible Duplicate")
		self.assertTrue(
			"missing or weak reference" in result["reason"]
			or "similar narration" in result["reason"]
		)

	@patch("retailedge.bank_transaction_bridge.get_bank_transaction_meta_fields", return_value={"bank_account": {}, "date": {}, "deposit": {}, "reference_number": {}})
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	def test_same_date_amount_weak_reference_is_possible_duplicate(self, mock_get_all, _mock_meta):
		mock_get_all.side_effect = [[
			SimpleNamespace(
				name="ACC-BTN-0004",
				bank_account="Moniepoint - moniepoint",
				date="2026-05-22",
				deposit=1000.0,
				withdrawal=0.0,
				description="Customer transfer",
				reference_number="POS",
				status="Pending",
			)
		], []]
		result = find_existing_bank_transaction_duplicate(
			{
				"bank_account": "Moniepoint - moniepoint",
				"transaction_date": "2026-05-22",
				"amount": 1000.0,
				"direction": "Inflow",
				"normalized_reference": "POS",
				"reference_number": "POS",
				"description": "Customer transfer",
			}
		)
		self.assertTrue(result["is_duplicate"])
		self.assertEqual(result["duplicate_type"], "Possible Duplicate")

	@patch("retailedge.bank_transaction_bridge.get_bank_transaction_meta_fields", return_value={"bank_account": {}, "date": {}, "deposit": {}, "reference_number": {}})
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	def test_similar_narration_missing_reference_is_possible_duplicate(self, mock_get_all, _mock_meta):
		mock_get_all.side_effect = [[
			SimpleNamespace(
				name="ACC-BTN-0005",
				bank_account="Moniepoint - moniepoint",
				date="2026-05-22",
				deposit=1000.0,
				withdrawal=0.0,
				description="Customer transfer",
				reference_number="",
				status="Pending",
			)
		], []]
		result = find_existing_bank_transaction_duplicate(
			{
				"bank_account": "Moniepoint - moniepoint",
				"transaction_date": "2026-05-22",
				"amount": 1000.0,
				"direction": "Inflow",
				"normalized_reference": "",
				"reference_number": "",
				"description": "Customer transfer",
			}
		)
		self.assertTrue(result["is_duplicate"])
		self.assertIn("similar narration", result["reason"])

	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	def test_same_amount_alone_is_not_treated_as_exact_duplicate(self, mock_get_all):
		row = self._row_doc(name="ROW-NEW", transaction_date="2026-05-22", amount=1000.0, credit=1000.0)
		mock_get_all.side_effect = [
			[],
			[],
			[],
		]
		result = find_existing_statement_row_duplicate(
			row,
			normalized={
				"row_fingerprint": "abc123",
				"transaction_date": "2026-05-22",
				"amount": 1000.0,
				"direction": "Inflow",
				"normalized_reference": "TRF001998",
			},
		)
		self.assertFalse(result["is_duplicate"])

	@patch("retailedge.bank_transaction_bridge.frappe.get_cached_doc")
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	def test_same_date_amount_different_reliable_reference_is_not_duplicate_statement_row(self, mock_get_all, mock_get_cached_doc):
		row = self._row_doc(name="ROW-NEW")
		mock_get_cached_doc.return_value = self._import_doc()
		mock_get_all.side_effect = [
			[],
			[
				SimpleNamespace(
					name="ROW-OLD",
					parent="RE-PSI-OLD",
					reference="TRF999999",
					normalized_reference="TRF999999",
					bank_transaction=None,
					existing_bank_transaction=None,
				)
			],
			[],
		]
		result = find_existing_statement_row_duplicate(
			row,
			normalized={
				"row_fingerprint": "new-fingerprint",
				"transaction_date": "2026-05-22",
				"amount": 1000.0,
				"direction": "Inflow",
				"normalized_reference": "TRF001998",
				"company": "Process Edge (Demo)",
				"bank_account": "Moniepoint - moniepoint",
			},
		)
		self.assertFalse(result["is_duplicate"])

	@patch("retailedge.bank_transaction_bridge.frappe.get_cached_doc")
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	def test_same_date_amount_same_reliable_reference_is_exact_duplicate_statement_row(self, mock_get_all, mock_get_cached_doc):
		row = self._row_doc(name="ROW-NEW")
		mock_get_cached_doc.return_value = self._import_doc()
		mock_get_all.side_effect = [
			[
				SimpleNamespace(
					name="ROW-OLD",
					parent="RE-PSI-OLD",
					bank_transaction="ACC-BTN-OLD",
					existing_bank_transaction=None,
					import_status="Imported",
				)
			]
		]
		result = find_existing_statement_row_duplicate(
			row,
			normalized={
				"row_fingerprint": "new-fingerprint",
				"transaction_date": "2026-05-22",
				"amount": 1000.0,
				"direction": "Inflow",
				"normalized_reference": "TRF001998",
				"company": "Process Edge (Demo)",
				"bank_account": "Moniepoint - moniepoint",
			},
		)
		self.assertTrue(result["is_duplicate"])
		self.assertEqual(result["duplicate_type"], "Already Imported")

	@patch("retailedge.bank_transaction_bridge.frappe.get_cached_doc")
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	def test_same_date_amount_missing_reference_is_possible_duplicate_statement_row(self, mock_get_all, mock_get_cached_doc):
		row = self._row_doc(name="ROW-NEW", normalized_reference="", reference="")
		mock_get_cached_doc.return_value = self._import_doc()
		mock_get_all.side_effect = [
			[
				SimpleNamespace(
					name="ROW-OLD",
					parent="RE-PSI-OLD",
					reference="",
					normalized_reference="",
					bank_transaction=None,
					existing_bank_transaction=None,
				)
			],
		]
		result = find_existing_statement_row_duplicate(
			row,
			normalized={
				"row_fingerprint": "new-fingerprint",
				"transaction_date": "2026-05-22",
				"amount": 1000.0,
				"direction": "Inflow",
				"normalized_reference": "",
				"normalized_narration": "CUSTOMERTRANSFER",
				"company": "Process Edge (Demo)",
				"bank_account": "Moniepoint - moniepoint",
			},
		)
		self.assertTrue(result["is_duplicate"])
		self.assertEqual(result["duplicate_type"], "Possible Duplicate")
		self.assertIn("missing or weak reference", result["reason"])

	@patch("retailedge.bank_transaction_bridge.get_bank_transaction_meta_fields", return_value={"bank_account": {}, "date": {}, "deposit": {}, "reference_number": {}})
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	def test_different_direction_with_same_date_amount_reference_is_not_exact_duplicate(self, mock_get_all, _mock_meta):
		mock_get_all.side_effect = [
			[],
			[
				SimpleNamespace(
					name="ACC-BTN-0006",
					reference_number="TRF001998",
					description="Customer transfer",
					date="2026-05-22",
					deposit=0.0,
					withdrawal=1000.0,
					bank_account="Moniepoint - moniepoint",
				)
			],
		]
		result = find_existing_bank_transaction_duplicate(
			{
				"bank_account": "Moniepoint - moniepoint",
				"transaction_date": "2026-05-22",
				"amount": 1000.0,
				"direction": "Inflow",
				"normalized_reference": "TRF001998",
				"reference_number": "TRF001998",
				"description": "Customer transfer",
			}
		)
		self.assertFalse(result["is_duplicate"])

	@patch("retailedge.bank_transaction_bridge.get_bank_transaction_meta_fields", return_value={"bank_account": {}, "date": {}, "deposit": {}, "reference_number": {}})
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	def test_different_bank_account_with_same_date_amount_reference_is_not_exact_duplicate(self, mock_get_all, _mock_meta):
		mock_get_all.side_effect = [[], []]
		result = find_existing_bank_transaction_duplicate(
			{
				"bank_account": "Moniepoint - moniepoint",
				"transaction_date": "2026-05-22",
				"amount": 1000.0,
				"direction": "Inflow",
				"normalized_reference": "TRF001998",
				"reference_number": "TRF001998",
				"description": "Customer transfer",
			}
		)
		self.assertFalse(result["is_duplicate"])

	@patch("retailedge.bank_transaction_bridge.find_existing_bank_transaction_duplicate", return_value={"is_duplicate": False, "duplicate_type": None, "statement_row": None, "bank_transaction": None, "reason": None})
	@patch("retailedge.bank_transaction_bridge.find_existing_statement_row_duplicate", return_value={"is_duplicate": False, "duplicate_type": None, "statement_row": None, "bank_transaction": None, "reason": None})
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	def test_dry_run_does_not_create_bank_transaction(self, mock_get_doc, _mock_row_duplicate, _mock_bank_duplicate):
		row = self._row_doc()
		parent = self._import_doc()
		mock_get_doc.side_effect = lambda doctype, name: row if doctype == "RetailEdge Statement Import Row" else parent
		with patch("retailedge.bank_transaction_bridge._create_bank_transaction") as mock_create:
			result = create_or_link_bank_transaction_from_statement_row(row.name, dry_run=True)
		self.assertEqual(result["status"], "Would Import")
		mock_create.assert_not_called()

	@patch("retailedge.bank_transaction_bridge._update_statement_row_bridge_fields")
	@patch("retailedge.bank_transaction_bridge._create_bank_transaction", return_value="ACC-BTN-0003")
	@patch("retailedge.bank_transaction_bridge.find_existing_bank_transaction_duplicate", return_value={"is_duplicate": False, "duplicate_type": None, "statement_row": None, "bank_transaction": None, "reason": None})
	@patch("retailedge.bank_transaction_bridge.find_existing_statement_row_duplicate", return_value={"is_duplicate": False, "duplicate_type": None, "statement_row": None, "bank_transaction": None, "reason": None})
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	def test_non_dry_run_creates_bank_transaction_for_valid_row(
		self,
		mock_get_doc,
		_mock_row_duplicate,
		_mock_bank_duplicate,
		mock_create_bank_transaction,
		mock_update_row,
	):
		row = self._row_doc()
		parent = self._import_doc()
		mock_get_doc.side_effect = lambda doctype, name: row if doctype == "RetailEdge Statement Import Row" else parent
		result = create_or_link_bank_transaction_from_statement_row(row.name, dry_run=False)
		self.assertEqual(result["status"], "Imported")
		self.assertEqual(result["bank_transaction"], "ACC-BTN-0003")
		mock_create_bank_transaction.assert_called_once()
		mock_update_row.assert_called_once()

	@patch("retailedge.bank_transaction_bridge._update_statement_row_bridge_fields")
	@patch("retailedge.bank_transaction_bridge.find_existing_bank_transaction_duplicate", return_value={"is_duplicate": True, "duplicate_type": "Already Imported", "statement_row": None, "bank_transaction": "ACC-BTN-0004", "reason": "Existing transaction found"})
	@patch("retailedge.bank_transaction_bridge.find_existing_statement_row_duplicate", return_value={"is_duplicate": False, "duplicate_type": None, "statement_row": None, "bank_transaction": None, "reason": None})
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	def test_existing_bank_transaction_is_linked_instead_of_creating_duplicate(
		self,
		mock_get_doc,
		_mock_row_duplicate,
		_mock_bank_duplicate,
		mock_update_row,
	):
		row = self._row_doc()
		parent = self._import_doc()
		mock_get_doc.side_effect = lambda doctype, name: row if doctype == "RetailEdge Statement Import Row" else parent
		with patch("retailedge.bank_transaction_bridge._create_bank_transaction") as mock_create:
			result = create_or_link_bank_transaction_from_statement_row(row.name, dry_run=False)
		self.assertEqual(result["status"], "Already Imported")
		self.assertEqual(result["bank_transaction"], "ACC-BTN-0004")
		mock_create.assert_not_called()
		mock_update_row.assert_called_once()

	@patch("retailedge.bank_transaction_bridge._update_statement_row_bridge_fields")
	@patch("retailedge.bank_transaction_bridge.find_existing_bank_transaction_duplicate", return_value={"is_duplicate": False, "duplicate_type": None, "statement_row": None, "bank_transaction": None, "reason": None})
	@patch("retailedge.bank_transaction_bridge.find_existing_statement_row_duplicate", return_value={"is_duplicate": True, "duplicate_type": "Exact Duplicate", "statement_row": "ROW-OLD", "bank_transaction": None, "reason": "Duplicate row"})
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	def test_duplicate_row_is_skipped_by_default(
		self,
		mock_get_doc,
		_mock_row_duplicate,
		_mock_bank_duplicate,
		mock_update_row,
	):
		row = self._row_doc()
		parent = self._import_doc()
		mock_get_doc.side_effect = lambda doctype, name: row if doctype == "RetailEdge Statement Import Row" else parent
		with patch("retailedge.bank_transaction_bridge._create_bank_transaction") as mock_create:
			result = create_or_link_bank_transaction_from_statement_row(row.name, dry_run=False)
		self.assertEqual(result["status"], "Exact Duplicate")
		mock_create.assert_not_called()
		mock_update_row.assert_called_once()

	@patch("retailedge.bank_transaction_bridge._update_statement_row_bridge_fields")
	@patch("retailedge.bank_transaction_bridge._create_bank_transaction", return_value="ACC-BTN-NEW")
	@patch("retailedge.bank_transaction_bridge.find_existing_bank_transaction_duplicate", return_value={"is_duplicate": True, "duplicate_type": "Possible Duplicate", "statement_row": None, "bank_transaction": "ACC-BTN-OLD", "reason": "Narration looks similar"})
	@patch("retailedge.bank_transaction_bridge.find_existing_statement_row_duplicate", return_value={"is_duplicate": False, "duplicate_type": None, "statement_row": None, "bank_transaction": None, "reason": None})
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	def test_force_import_allows_possible_duplicate_row_to_create_new_bank_transaction(
		self,
		mock_get_doc,
		_mock_row_duplicate,
		_mock_bank_duplicate,
		mock_create_bank_transaction,
		mock_update_row,
	):
		row = self._row_doc(name="ROW-FORCE")
		parent = self._import_doc()
		mock_get_doc.side_effect = lambda doctype, name: row if doctype == "RetailEdge Statement Import Row" else parent
		result = create_or_link_bank_transaction_from_statement_row(row.name, force=True, dry_run=False)
		self.assertEqual(result["status"], "Imported")
		self.assertEqual(result["bank_transaction"], "ACC-BTN-NEW")
		mock_create_bank_transaction.assert_called_once()
		mock_update_row.assert_called_once()

	@patch("retailedge.bank_transaction_bridge.create_or_link_bank_transaction_from_statement_row")
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	def test_bulk_preview_returns_correct_summary(self, mock_get_doc, mock_get_all, mock_bridge):
		mock_get_doc.return_value = self._import_doc()
		mock_get_all.return_value = [SimpleNamespace(name="ROW-1"), SimpleNamespace(name="ROW-2")]
		mock_bridge.side_effect = [
			{"statement_row": "ROW-1", "status": "Would Import"},
			{"statement_row": "ROW-2", "status": "Already Imported"},
		]
		result = preview_bank_transaction_import("RE-PSI-0001")
		self.assertEqual(result["total_rows"], 2)
		self.assertEqual(result["would_import"], 1)
		self.assertEqual(result["already_imported"], 1)
		self.assertIn("imported_rows", result)
		self.assertIn("duplicate_rows", result)
		self.assertIn("linked_bank_transactions", result)

	@patch("retailedge.bank_transaction_bridge.frappe.db.commit")
	@patch("retailedge.bank_transaction_bridge._refresh_statement_import_bridge_summary")
	@patch("retailedge.bank_transaction_bridge.create_or_link_bank_transaction_from_statement_row")
	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	def test_bulk_import_updates_parent_summary_fields(
		self,
		mock_get_doc,
		mock_get_all,
		mock_bridge,
		mock_refresh_summary,
		_mock_commit,
	):
		mock_get_doc.return_value = self._import_doc()
		mock_get_all.return_value = [SimpleNamespace(name="ROW-1"), SimpleNamespace(name="ROW-2")]
		mock_bridge.side_effect = [
			{"statement_row": "ROW-1", "status": "Imported"},
			{"statement_row": "ROW-2", "status": "Already Imported"},
		]
		result = import_statement_rows_to_bank_transactions("RE-PSI-0001")
		self.assertEqual(result["imported"], 1)
		self.assertEqual(result["already_imported"], 1)
		mock_refresh_summary.assert_called_once()

	@patch("retailedge.bank_transaction_bridge.frappe.db.commit")
	@patch("retailedge.bank_transaction_bridge._refresh_statement_import_bridge_summary")
	@patch("retailedge.bank_transaction_bridge.frappe.db.set_value")
	@patch("retailedge.bank_transaction_bridge.now_datetime", return_value="2026-05-23 10:00:00")
	@patch("retailedge.bank_transaction_bridge.create_or_link_bank_transaction_from_statement_row", return_value={"status": "Imported", "reason": "Imported cleanly", "bank_transaction": "ACC-BTN-0007"})
	@patch("retailedge.bank_transaction_bridge.find_existing_bank_transaction_duplicate", return_value={"is_duplicate": True, "duplicate_type": "Possible Duplicate", "bank_transaction": "ACC-BTN-OLD", "reason": "Possible duplicate"})
	@patch("retailedge.bank_transaction_bridge.find_existing_statement_row_duplicate", return_value={"is_duplicate": False, "duplicate_type": None, "statement_row": None, "bank_transaction": None, "reason": None})
	@patch("retailedge.bank_transaction_bridge.frappe.get_cached_doc")
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	def test_possible_duplicate_can_be_manually_accepted(
		self,
		mock_get_doc,
		mock_get_cached_doc,
		_mock_statement_duplicate,
		_mock_bank_duplicate,
		mock_import,
		_mock_now_datetime,
		mock_set_value,
		mock_refresh_summary,
		_mock_commit,
	):
		row = self._row_doc(name="ROW-POSSIBLE", duplicate_status="Possible Duplicate", import_status="Skipped")
		parent = self._import_doc()
		mock_get_doc.side_effect = lambda doctype, name: row if doctype == "RetailEdge Statement Import Row" else parent
		mock_get_cached_doc.return_value = parent
		with patch("retailedge.bank_transaction_bridge.frappe.session", SimpleNamespace(user="manager@example.com")):
			result = accept_possible_duplicate_statement_row("ROW-POSSIBLE", acceptance_note="Valid repeated amount")
		self.assertEqual(result["status"], "Manually Accepted")
		mock_import.assert_called_once_with("ROW-POSSIBLE", force=True, dry_run=False)
		mock_set_value.assert_called_once()
		values = mock_set_value.call_args[0][2]
		self.assertEqual(values["duplicate_status"], "Accepted Possible Duplicate")
		self.assertEqual(values["import_status"], "Manually Accepted")
		self.assertEqual(values["accepted_by"], "manager@example.com")
		mock_refresh_summary.assert_called_once()

	@patch("retailedge.bank_transaction_bridge.find_existing_bank_transaction_duplicate", return_value={"is_duplicate": True, "duplicate_type": "Already Imported", "bank_transaction": "ACC-BTN-EXACT", "reason": "Exact duplicate exists"})
	@patch("retailedge.bank_transaction_bridge.find_existing_statement_row_duplicate", return_value={"is_duplicate": False, "duplicate_type": None, "statement_row": None, "bank_transaction": None, "reason": None})
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	def test_exact_duplicate_cannot_be_manually_accepted(
		self,
		mock_get_doc,
		_mock_statement_duplicate,
		_mock_bank_duplicate,
	):
		row = self._row_doc(name="ROW-BLOCK", duplicate_status="Possible Duplicate", import_status="Skipped")
		parent = self._import_doc()
		mock_get_doc.side_effect = lambda doctype, name: row if doctype == "RetailEdge Statement Import Row" else parent
		with self.assertRaises(Exception):
			accept_possible_duplicate_statement_row("ROW-BLOCK", acceptance_note="Should fail")

	def test_import_summary_json_is_hidden_from_normal_form_display(self):
		with open(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_payment_statement_import/retailedge_payment_statement_import.json",
			encoding="utf-8",
		) as handle:
			doc = json.load(handle)
		field = next(item for item in doc["fields"] if item.get("fieldname") == "import_summary_json")
		self.assertEqual(field.get("hidden"), 1)
		self.assertEqual(field.get("no_copy"), 1)

	def test_friendly_summary_script_does_not_dump_raw_json(self):
		with open(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_payment_statement_import/retailedge_payment_statement_import.js",
			encoding="utf-8",
		) as handle:
			script = handle.read()
		self.assertIn("build_statement_import_summary_html", script)
		self.assertNotIn("JSON.stringify(result, null, 2)", script)
		self.assertIn('__("Review Possible Duplicates")', script)

	def test_payment_statement_import_js_has_review_possible_duplicates_under_bank_transactions(self):
		with open(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_payment_statement_import/retailedge_payment_statement_import.js",
			encoding="utf-8",
		) as handle:
			script = handle.read()
		self.assertIn('__("Review Possible Duplicates")', script)
		self.assertIn('__("Bank Transactions")', script)

	def test_parent_api_wrapper_for_possible_duplicates_exists(self):
		api = importlib.import_module("retailedge.api")
		self.assertTrue(callable(getattr(api, "get_possible_duplicate_statement_rows", None)))

	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	def test_get_possible_duplicate_statement_rows_returns_rows_for_parent_import(self, mock_get_doc, mock_get_all):
		mock_get_doc.return_value = self._import_doc(name="RE-PSI-0002", bank_account="Moniepoint - moniepoint")
		mock_get_all.return_value = [
			SimpleNamespace(
				name="ROW-PD-1",
				transaction_date="2026-05-24",
				reference="",
				narration="Customer transfer",
				amount=1000.0,
				transaction_direction="Inflow",
				direction="Credit",
				duplicate_status="Possible Duplicate",
				import_status="Skipped",
				row_error="Possible duplicate: same date and amount with missing or weak reference.",
				duplicate_reason=None,
				existing_bank_transaction="ACC-BTN-0001",
				bank_transaction=None,
			),
			SimpleNamespace(
				name="ROW-EXACT",
				transaction_date="2026-05-24",
				reference="TRF001",
				narration="Duplicate",
				amount=1000.0,
				transaction_direction="Inflow",
				direction="Credit",
				duplicate_status="Exact Duplicate",
				import_status="Skipped",
				row_error="Exact duplicate",
				duplicate_reason=None,
				existing_bank_transaction="ACC-BTN-0002",
				bank_transaction=None,
			),
		]
		rows = get_possible_duplicate_statement_rows("RE-PSI-0002")
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["name"], "ROW-PD-1")
		self.assertEqual(rows[0]["bank_account"], "Moniepoint - moniepoint")
		self.assertEqual(rows[0]["existing_bank_transaction"], "ACC-BTN-0001")

	@patch("retailedge.bank_transaction_bridge.frappe.get_all")
	@patch("retailedge.bank_transaction_bridge.frappe.get_doc")
	def test_get_possible_duplicate_statement_rows_does_not_return_exact_duplicates_as_reviewable(self, mock_get_doc, mock_get_all):
		mock_get_doc.return_value = self._import_doc(name="RE-PSI-0003")
		mock_get_all.return_value = [
			SimpleNamespace(
				name="ROW-EXACT",
				transaction_date="2026-05-24",
				reference="TRF001",
				narration="Duplicate",
				amount=1000.0,
				transaction_direction="Inflow",
				direction="Credit",
				duplicate_status="Exact Duplicate",
				import_status="Already Imported",
				row_error="Exact duplicate",
				duplicate_reason=None,
				existing_bank_transaction="ACC-BTN-0002",
				bank_transaction=None,
			)
		]
		rows = get_possible_duplicate_statement_rows("RE-PSI-0003")
		self.assertEqual(rows, [])

	@patch("retailedge.bank_transaction_bridge.frappe.new_doc")
	@patch("retailedge.bank_transaction_bridge.get_bank_transaction_meta_fields")
	def test_create_bank_transaction_uses_only_bank_transaction_doctype(self, mock_meta, mock_new_doc):
		mock_meta.return_value = {
			"bank_account": {},
			"date": {},
			"deposit": {},
			"withdrawal": {},
			"currency": {},
			"description": {},
			"reference_number": {},
		}
		doc = MagicMock()
		doc.name = "ACC-BTN-0099"
		mock_new_doc.return_value = doc
		with patch("retailedge.bank_transaction_bridge.find_existing_statement_row_duplicate", return_value={"is_duplicate": False, "duplicate_type": None, "statement_row": None, "bank_transaction": None, "reason": None}), patch(
			"retailedge.bank_transaction_bridge.find_existing_bank_transaction_duplicate",
			return_value={"is_duplicate": False, "duplicate_type": None, "statement_row": None, "bank_transaction": None, "reason": None},
		), patch("retailedge.bank_transaction_bridge._update_statement_row_bridge_fields"), patch(
			"retailedge.bank_transaction_bridge.frappe.get_doc"
		) as mock_get_doc:
			row = self._row_doc()
			parent = self._import_doc()
			mock_get_doc.side_effect = lambda doctype, name: row if doctype == "RetailEdge Statement Import Row" else parent
			create_or_link_bank_transaction_from_statement_row(row.name, dry_run=False)
		mock_new_doc.assert_called_once_with("Bank Transaction")


if __name__ == "__main__":
	unittest.main()
