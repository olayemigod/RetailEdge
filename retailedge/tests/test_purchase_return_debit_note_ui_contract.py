from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPurchaseReturnDebitNoteUIContract(TestCase):
	def test_professional_purchasing_exposes_two_distinct_guided_return_actions(self):
		component = (APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchasing.vue").read_text()

		self.assertIn("Returns & Supplier Credits", component)
		self.assertIn("Return Received Goods", component)
		self.assertIn("Create Supplier Debit Note", component)
		self.assertIn('label="Submitted Purchase Receipt"', component)
		self.assertIn('label="Submitted Purchase Invoice"', component)
		self.assertIn("preparePurchaseReturn", component)
		self.assertIn("prepareSupplierDebitNote", component)
		self.assertNotIn("Return + Debit Note", component)
		self.assertNotIn("return_and_debit", component)

	def test_ui_uses_backend_filtered_sources_and_clears_dependent_selections(self):
		component = (APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchasing.vue").read_text()

		self.assertIn("retailedge.professional_purchasing.search_purchase_return_sources", component)
		self.assertIn('this.searchReturnSources("purchase_receipt", txt)', component)
		self.assertIn('this.searchReturnSources("purchase_invoice", txt)', component)
		self.assertIn("company: this.filters.company || null", component)
		self.assertIn("branch: this.filters.branch || null", component)
		self.assertIn("supplier: this.filters.supplier || null", component)
		self.assertIn("clearReturnSources(); this.loadWorkspace()", component)
		self.assertIn('this.returnSources = { purchaseReceipt: "", purchaseInvoice: "" }', component)

	def test_success_handoff_routes_to_native_erpnext_drafts(self):
		component = (APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchasing.vue").read_text()

		self.assertIn("retailedge.professional_purchasing.prepare_purchase_return_draft", component)
		self.assertIn("retailedge.professional_purchasing.prepare_supplier_debit_note_draft", component)
		self.assertIn('frappe.set_route("Form", "Purchase Receipt", result.name)', component)
		self.assertIn('frappe.set_route("Form", "Purchase Invoice", result.name)', component)
		self.assertIn("ERPNext Update Stock remains enabled", component)
		self.assertIn("never chains a stock return and supplier debit note automatically", component)

	def test_existing_professional_purchasing_flows_and_edgesuite_runtime_remain(self):
		component = (APP_ROOT / "public" / "js" / "professional_purchasing" / "ProfessionalPurchasing.vue").read_text()

		self.assertIn("Purchase Material Requests", component)
		self.assertIn("Prepare Draft RFQ", component)
		self.assertIn("Prepare Receipt", component)
		self.assertIn("EdgeLinkField", component)
		self.assertIn("window.EdgeSuiteUI?.components", component)
		self.assertNotIn("frappe.ui.Dialog", component)
		self.assertNotIn("frappe.prompt", component)
		self.assertNotIn("frappe.msgprint", component)
		self.assertNotIn("frappe.show_alert", component)
		self.assertNotIn("window.EdgeUI", component)

	def test_backend_contract_is_native_draft_first_without_direct_posting(self):
		source = (APP_ROOT / "professional_purchasing.py").read_text()

		self.assertIn("make_purchase_return(source.name)", source)
		self.assertIn("make_debit_note(source.name)", source)
		self.assertIn("target.insert()", source)
		self.assertIn('"posting_status": "Draft"', source)
		self.assertIn("validate_user_branch_access", source)
		self.assertIn('filters.update({"docstatus": 1, "is_return": 0})', source)
		self.assertNotIn(".submit(", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)
		self.assertNotIn('frappe.new_doc("Payment Entry")', source)
		self.assertNotIn('frappe.new_doc("Journal Entry")', source)


if __name__ == "__main__":
	import unittest

	unittest.main()
