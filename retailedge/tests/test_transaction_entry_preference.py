from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.transaction_entry_preference import (
	DEFAULT_PREFERENCE,
	USER_DEFAULT_KEY,
	get_transaction_entry_style,
	set_transaction_entry_preference,
)


ROOT = Path(__file__).resolve().parents[1]


class TestTransactionEntryPreference(unittest.TestCase):
	@patch("retailedge.transaction_entry_preference.frappe.defaults.get_user_default", return_value=None)
	def test_missing_preference_defaults_to_smart(self, mock_get):
		self.assertEqual(get_transaction_entry_style(user="user@example.com"), DEFAULT_PREFERENCE)
		mock_get.assert_called_once_with(USER_DEFAULT_KEY, user="user@example.com")

	@patch("retailedge.transaction_entry_preference.frappe.defaults.get_user_default", return_value="full")
	def test_saved_preference_is_user_scoped(self, _mock_get):
		self.assertEqual(get_transaction_entry_style(user="user@example.com"), "full")

	@patch("retailedge.transaction_entry_preference.frappe.defaults.set_user_default")
	def test_set_preference_writes_only_current_user_default(self, mock_set):
		with patch.object(frappe.session, "user", "user@example.com"):
			result = set_transaction_entry_preference("quick")
		self.assertEqual(result["value"], "quick")
		self.assertEqual(result["scope"], "user")
		mock_set.assert_called_once_with(USER_DEFAULT_KEY, "quick", user="user@example.com")

	def test_invalid_preference_fails_closed(self):
		with patch.object(frappe.session, "user", "user@example.com"):
			with self.assertRaises(frappe.ValidationError):
				set_transaction_entry_preference("always_popup_forever")

	def test_edgesuite_surfaces_respect_user_preference_without_removing_explicit_choice(self):
		utils = (ROOT / "public/js/retailedge_business_hub/guidedEntryUtils.js").read_text(encoding="utf-8")
		hub = (ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue").read_text(encoding="utf-8")
		workspace = (ROOT / "public/js/transaction_workspace/TransactionWorkspace.vue").read_text(encoding="utf-8")
		context = (ROOT / "public/js/operating_context/OperatingContext.vue").read_text(encoding="utf-8")

		for contract in (
			"getTransactionEntryPreference",
			"setTransactionEntryPreference",
			'"Sales Invoice": "make-sale"',
			'"Purchase Invoice": "record-purchase"',
			'"Stock Entry": "transfer-stock"',
			'"Stock Reconciliation": "stock-adjustment"',
		):
			self.assertIn(contract, utils)

		self.assertIn('preference.value === "full"', hub)
		self.assertIn("hasPageTarget(target)", hub)
		self.assertIn("getTransactionEntryPreference({ force: true })", hub)
		self.assertIn('entryPreference !== "quick"', workspace)
		self.assertIn("getTransactionEntryPreference({ force: true })", workspace)
		self.assertIn("runAlternateTransactionAction", workspace)
		self.assertIn("Quick Sale", workspace)
		self.assertIn("Make Sale Page", workspace)

		for contract in (
			"Personal transaction preference",
			"Transaction Entry Style",
			"Smart",
			"Quick Entry",
			"Full Page",
			"set_transaction_entry_preference",
		):
			self.assertIn(contract, context)

	def test_full_page_preference_can_edit_existing_standard_sales_invoice_without_recreating_it(self):
		selling = (ROOT / "public/js/professional_selling/ProfessionalSelling.vue").read_text(encoding="utf-8")
		make_sale = (ROOT / "public/js/make_sale/MakeSale.vue").read_text(encoding="utf-8")
		for contract in (
			"openSalesInvoiceDraftOnPage",
			"document_name: name",
			'preference?.value === "full"',
			'!row.is_return',
		):
			self.assertIn(contract, selling)
		for contract in (
			"consumeSavedDraftHandoff",
			"get_standard_sales_invoice_completion_preview",
			"editingSavedDraft = true",
			"syncPageFromDraftPreview(preview)",
			"Return / Credit Note drafts remain in the governed return review",
		):
			self.assertIn(contract, make_sale)

	def test_full_page_preference_routes_direct_purchase_draft_to_record_purchase(self):
		purchasing = (ROOT / "public/js/professional_purchasing/ProfessionalPurchasing.vue").read_text(encoding="utf-8")
		record_purchase = (ROOT / "public/js/record_purchase/RecordPurchase.vue").read_text(encoding="utf-8")
		for contract in (
			"getTransactionEntryPreference({ force: true })",
			'preference?.value === "full"',
			' effectiveMode === "direct"',
			"openPurchaseInvoiceDraftOnPage",
			"document_name: name",
			'frappe.set_route("record-purchase")',
		):
			self.assertIn(contract.strip(), purchasing)
		for contract in (
			"consumeSavedDraftHandoff",
			'source_mode: "direct"',
			"editingSavedDraft = true",
			"syncPageFromDraftPreview(preview)",
		):
			self.assertIn(contract, record_purchase)

	def test_existing_quick_entry_line_limit_and_safe_exit_remain_intact(self):
		utils = (ROOT / "public/js/retailedge_business_hub/guidedEntryUtils.js").read_text(encoding="utf-8")
		sale = (ROOT / "public/js/retailedge_business_hub/SimpleSalesInvoiceDialog.vue").read_text(encoding="utf-8")
		make_sale = (ROOT / "public/js/make_sale/MakeSale.vue").read_text(encoding="utf-8")
		self.assertIn("export const QUICK_ENTRY_MAX_LINES = 10;", utils)
		self.assertIn("Discard the unsaved Quick Sale changes?", sale)
		self.assertIn("Continue in Make Sale", sale)
		self.assertIn("sessionStorage", make_sale)
		self.assertIn("beforeunload", make_sale)


if __name__ == "__main__":
	unittest.main()
