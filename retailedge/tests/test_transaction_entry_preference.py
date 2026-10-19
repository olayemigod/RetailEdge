from pathlib import Path

from frappe.tests import IntegrationTestCase


ROOT = Path(__file__).resolve().parents[1]


class TestTransactionEntryPreference(IntegrationTestCase):
	def test_preference_contract_is_shared_across_transaction_entry_surfaces(self):
		context = (ROOT / "transaction_entry_preference.py").read_text(encoding="utf-8")
		utils = (ROOT / "public/js/retailedge_business_hub/guidedEntryUtils.js").read_text(encoding="utf-8")
		for contract in (
			"setTransactionEntryPreference",
			"getTransactionEntryPreference({ force: true })",
		):
			self.assertIn(contract, context)
		self.assertIn("selection = null", context)
		self.assertIn("ENTRY_PREFERENCE_LABELS[rawValue]", context)
		self.assertIn("__retailedgeTransactionEntryPreferenceCache", utils)
		self.assertIn("readSharedTransactionEntryPreferenceCache", utils)
		self.assertIn("writeSharedTransactionEntryPreferenceCache", utils)

	def test_professional_selling_honours_full_page_and_popup_escape_for_new_sales(self):
		selling = (ROOT / "public/js/professional_selling/ProfessionalSelling.vue").read_text(encoding="utf-8")
		dialog = (ROOT / "public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue").read_text(encoding="utf-8")
		for contract in (
			"async startCreate(document)",
			'preference?.value === "full"',
			'hasPageTarget("make-sale")',
			'frappe.set_route("make-sale")',
			'@open-page="openNewSalesInvoiceOnPage"',
			"retailedge:make-sale:handoff:",
		):
			self.assertIn(contract, selling)
		for contract in (
			"Continue in Make Sale",
			"openMakeSalePage",
			'"open-page"',
		):
			self.assertIn(contract, dialog)

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

	def test_persistent_transaction_pages_are_declared_once(self):
		utils = (ROOT / "public/js/retailedge_business_hub/guidedEntryUtils.js").read_text(encoding="utf-8")
		for contract in (
			'"Sales Invoice": "make-sale"',
			'"Purchase Invoice": "record-purchase"',
			'"Stock Entry": "transfer-stock"',
			'"Stock Reconciliation": "stock-adjustment"',
		):
			self.assertIn(contract, utils)
