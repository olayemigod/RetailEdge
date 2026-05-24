from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import retailedge.api as retailedge_api
from retailedge.sales_invoice_verification_sync import (
	ensure_sales_invoice_verification_custom_fields,
	sync_bank_verified_sales_invoice_from_bank_transaction,
	sync_cash_verified_sales_invoices_for_shift,
	sync_sales_invoice_payment_verification,
)


APP_ROOT = Path(__file__).resolve().parents[2]


class SalesInvoiceVerificationSyncTests(unittest.TestCase):
	def _invoice(self, **kwargs):
		defaults = dict(
			doctype="Sales Invoice",
			name="SINV-0001",
			customer="Customer A",
			posting_date="2026-05-21",
			grand_total=1000.0,
			rounded_total=1000.0,
			outstanding_amount=1000.0,
			status="Unpaid",
			docstatus=1,
			retailedge_payment_verification_status="Unverified",
			payments=[],
		)
		defaults.update(kwargs)
		return SimpleNamespace(**defaults)

	def test_deleted_payment_matching_modules_are_removed(self):
		self.assertFalse((APP_ROOT / "retailedge" / ("payment" + "_evidence_" + "matching.py")).exists())
		self.assertFalse((APP_ROOT / "retailedge" / ("payment_" + "verification.py")).exists())

	def test_api_imports_cleanly(self):
		self.assertTrue(hasattr(retailedge_api, "preview_cash_sales_invoice_verification_sync"))
		self.assertTrue(hasattr(retailedge_api, "sync_bank_sales_invoice_verification"))

	def test_workspace_sidebar_does_not_expose_deleted_doctypes(self):
		sidebar = json.loads((APP_ROOT / "retailedge" / "workspace_sidebar" / "retailedge.json").read_text())
		links = [row.get("link_to") for row in sidebar.get("items", []) if row.get("type") == "Link"]
		self.assertNotIn("RetailEdge Payment Evidence " + "Matching", links)
		self.assertNotIn("RetailEdge Payment Evidence " + "Match", links)
		self.assertIn("RetailEdge Payment Statement Import", links)
		self.assertIn("RetailEdge Statement Mapping Template", links)

	def test_statement_import_foundation_files_exist(self):
		self.assertTrue((APP_ROOT / "retailedge" / "retailedge" / "doctype" / "retailedge_payment_statement_import" / "retailedge_payment_statement_import.json").exists())
		self.assertTrue((APP_ROOT / "retailedge" / "retailedge" / "doctype" / "retailedge_statement_import_row" / "retailedge_statement_import_row.json").exists())
		self.assertTrue((APP_ROOT / "retailedge" / "retailedge" / "doctype" / "retailedge_statement_mapping_template" / "retailedge_statement_mapping_template.json").exists())

	@patch("retailedge.sales_invoice_verification_sync.create_custom_fields")
	@patch("retailedge.sales_invoice_verification_sync.frappe.db.exists", return_value=True)
	def test_sales_invoice_verification_custom_fields_are_defined(self, _mock_exists, mock_create_custom_fields):
		ensure_sales_invoice_verification_custom_fields()
		custom_fields = mock_create_custom_fields.call_args.args[0]["Sales Invoice"]
		fieldnames = [row["fieldname"] for row in custom_fields]
		self.assertIn("retailedge_payment_verification_status", fieldnames)
		self.assertIn("retailedge_verified_amount", fieldnames)
		self.assertIn("retailedge_last_sync_on", fieldnames)

	@patch("retailedge.sales_invoice_verification_sync.assert_sales_invoice_verification_fields")
	@patch("retailedge.sales_invoice_verification_sync.now_datetime", return_value="2026-05-21 10:00:00")
	@patch("retailedge.sales_invoice_verification_sync.frappe.get_doc")
	@patch("retailedge.sales_invoice_verification_sync.frappe.db.set_value")
	@patch("retailedge.sales_invoice_verification_sync.frappe.db.exists", return_value=True)
	def test_sync_sales_invoice_payment_verification_updates_only_retailedge_fields(
		self, _mock_exists, mock_set_value, mock_get_doc, _mock_now, _mock_assert_fields
	):
		invoice = self._invoice()
		mock_get_doc.return_value = invoice
		result = sync_sales_invoice_payment_verification(
			invoice_name=invoice.name,
			status="Bank Verified",
			source="Bank Transaction Matching",
			verified_amount=600,
			reference="BTX-0001",
			note="Matched safely",
			verified_on="2026-05-21 10:00:00",
		)
		self.assertEqual(result["status"], "Bank Verified")
		args = mock_set_value.call_args.args
		self.assertEqual(args[0], "Sales Invoice")
		self.assertEqual(args[1], invoice.name)
		self.assertEqual(set(args[2].keys()), {
			"retailedge_payment_verification_status",
			"retailedge_payment_verification_source",
			"retailedge_verified_amount",
			"retailedge_unverified_amount",
			"retailedge_payment_variance",
			"retailedge_verified_by",
			"retailedge_verified_on",
			"retailedge_verification_reference",
			"retailedge_verification_note",
			"retailedge_last_sync_on",
		})
		self.assertNotIn("status", args[2])
		self.assertNotIn("outstanding_amount", args[2])
		self.assertNotIn("paid_amount", args[2])

	@patch("retailedge.sales_invoice_verification_sync.assert_sales_invoice_verification_fields")
	@patch("retailedge.sales_invoice_verification_sync._resolve_cash_sync_context")
	@patch("retailedge.sales_invoice_verification_sync._get_candidate_shift_invoices")
	@patch("retailedge.sales_invoice_verification_sync.get_sales_invoice_payment_rows")
	@patch("retailedge.sales_invoice_verification_sync.sync_sales_invoice_payment_verification")
	def test_cash_sync_dry_run_returns_eligible_without_mutation(
		self,
		mock_sync_invoice,
		mock_payment_rows,
		mock_invoices,
		mock_context,
		_mock_assert_fields,
	):
		mock_context.return_value = {
			"opening_shift": "OPEN-1",
			"closing_shift": "CLOSE-1",
			"daily_sales_audit": "RE-DSA-0001",
			"opening_cash": 100.0,
			"cash_sales": 300.0,
			"included_cashier_expenses": 50.0,
			"expected_cash": 350.0,
			"actual_closing_cash": 350.0,
			"cash_variance": 0.0,
			"audit_status": "Approved",
		}
		mock_invoices.return_value = [self._invoice()]
		mock_payment_rows.return_value = [{"payment_category": "Cash", "base_amount": 300.0}]
		result = sync_cash_verified_sales_invoices_for_shift(daily_sales_audit="RE-DSA-0001", dry_run=True)
		self.assertEqual(result["eligible_invoice_count"], 1)
		self.assertEqual(result["synced_invoice_count"], 0)
		self.assertEqual(result["invoices"][0]["action"], "Would Sync")
		mock_sync_invoice.assert_not_called()

	@patch("retailedge.sales_invoice_verification_sync.assert_sales_invoice_verification_fields")
	@patch("retailedge.sales_invoice_verification_sync._resolve_cash_sync_context")
	@patch("retailedge.sales_invoice_verification_sync._get_candidate_shift_invoices")
	@patch("retailedge.sales_invoice_verification_sync.get_sales_invoice_payment_rows")
	@patch("retailedge.sales_invoice_verification_sync.sync_sales_invoice_payment_verification")
	def test_cash_sync_marks_only_cash_only_invoices(
		self,
		mock_sync_invoice,
		mock_payment_rows,
		mock_invoices,
		mock_context,
		_mock_assert_fields,
	):
		mock_context.return_value = {
			"opening_shift": "OPEN-1",
			"closing_shift": "CLOSE-1",
			"daily_sales_audit": "RE-DSA-0001",
			"opening_cash": 100.0,
			"cash_sales": 300.0,
			"included_cashier_expenses": 0.0,
			"expected_cash": 400.0,
			"actual_closing_cash": 400.0,
			"cash_variance": 0.0,
			"audit_status": "Approved",
		}
		cash_invoice = self._invoice(name="SINV-CASH")
		card_invoice = self._invoice(name="SINV-CARD")
		mock_invoices.return_value = [cash_invoice, card_invoice]
		mock_payment_rows.side_effect = [
			[{"payment_category": "Cash", "base_amount": 400.0}],
			[{"payment_category": "Card / POS", "base_amount": 400.0}],
		]
		result = sync_cash_verified_sales_invoices_for_shift(daily_sales_audit="RE-DSA-0001", dry_run=False)
		self.assertEqual(result["eligible_invoice_count"], 1)
		self.assertEqual(result["synced_invoice_count"], 1)
		self.assertEqual(result["invoices"][0]["action"], "Synced")
		self.assertEqual(result["invoices"][1]["action"], "Skipped")
		mock_sync_invoice.assert_called_once()

	@patch("retailedge.sales_invoice_verification_sync.assert_sales_invoice_verification_fields")
	@patch("retailedge.sales_invoice_verification_sync.frappe.get_doc")
	@patch("retailedge.sales_invoice_verification_sync.frappe.db.exists")
	@patch("retailedge.sales_invoice_verification_sync.sync_sales_invoice_payment_verification")
	def test_bank_sync_dry_run_does_not_update_invoice(self, mock_sync_invoice, mock_exists, mock_get_doc, _mock_assert_fields):
		mock_exists.side_effect = lambda doctype, name=None: doctype in {"Sales Invoice", "Bank Transaction"}
		mock_get_doc.return_value = self._invoice()
		result = sync_bank_verified_sales_invoice_from_bank_transaction("SINV-0001", "BTX-0001", 500, dry_run=True)
		self.assertEqual(result["action"], "Would Sync")
		mock_sync_invoice.assert_not_called()

	@patch("retailedge.sales_invoice_verification_sync.assert_sales_invoice_verification_fields")
	@patch("retailedge.sales_invoice_verification_sync.frappe.get_doc")
	@patch("retailedge.sales_invoice_verification_sync.frappe.db.exists")
	@patch("retailedge.sales_invoice_verification_sync.sync_sales_invoice_payment_verification")
	def test_bank_sync_non_dry_run_updates_sales_invoice_only(
		self, mock_sync_invoice, mock_exists, mock_get_doc, _mock_assert_fields
	):
		mock_exists.side_effect = lambda doctype, name=None: doctype in {"Sales Invoice", "Bank Transaction"}
		mock_get_doc.return_value = self._invoice()
		result = sync_bank_verified_sales_invoice_from_bank_transaction("SINV-0001", "BTX-0001", 500, dry_run=False)
		self.assertEqual(result["action"], "Synced")
		mock_sync_invoice.assert_called_once()
		self.assertEqual(mock_sync_invoice.call_args.kwargs["source"], "Bank Transaction Matching")
