from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestRIR2F3F17PurchaseReturnSupplierDebitNoteEdgeSuiteOwnershipContract(unittest.TestCase):
	def test_professional_purchasing_mounts_return_ownership_interceptor(self):
		bundle = (APP_ROOT / "public/js/professional_purchasing.bundle.js").read_text(encoding="utf-8")
		ownership = (APP_ROOT / "public/js/professional_purchasing/professionalPurchaseReturnOwnership.js").read_text(encoding="utf-8")

		self.assertIn("installProfessionalPurchaseReturnOwnership", bundle)
		self.assertIn("cleanupReturns = installProfessionalPurchaseReturnOwnership(target)", bundle)
		self.assertIn('root.addEventListener("click", handler, true)', ownership)
		self.assertIn("event.stopImmediatePropagation()", ownership)
		self.assertIn('data-retailedge-return-review', ownership)
		self.assertIn('source_type: sourceType, source_name: sourceName', ownership)
		self.assertIn("Review & Submit Return", ownership)
		self.assertIn("Review & Submit Debit Note", ownership)

	def test_overlay_owns_standard_review_and_submit_without_native_route(self):
		overlay = (APP_ROOT / "public/js/professional_purchasing/ProfessionalPurchaseReturnReviewOverlay.vue").read_text(encoding="utf-8")

		self.assertIn("retailedge.professional_purchase_returns.get_purchase_return_review", overlay)
		self.assertIn("retailedge.professional_purchase_returns.submit_purchase_return_review", overlay)
		self.assertIn("Submit Purchase Return", overlay)
		self.assertIn("Submit Supplier Debit Note", overlay)
		self.assertIn("expected_source_modified", overlay)
		self.assertIn('}, "POST")', overlay)
		self.assertIn("Advanced: Prepare in ERPNext", overlay)
		self.assertIn("nativeFallbackEnabled", overlay)
		self.assertIn('mode !== ACCESS_MODE', overlay)
		self.assertNotIn('frappe.set_route("Form", "Purchase Receipt"', overlay)
		self.assertNotIn('frappe.set_route("Form", "Purchase Invoice"', overlay)

	def test_preview_uses_canonical_mappers_without_persistence(self):
		backend = (APP_ROOT / "professional_purchase_returns.py").read_text(encoding="utf-8")
		preview_body = backend.split("def get_purchase_return_review", 1)[1].split("def submit_purchase_return_review", 1)[0]

		self.assertIn("make_purchase_return(source.name)", backend)
		self.assertIn("make_debit_note(source.name)", backend)
		self.assertIn("_validate_native_purchase_return_source", backend)
		self.assertIn("_validate_native_purchase_return_target", backend)
		self.assertIn('"persistence": "none"', backend)
		self.assertNotIn(".insert()", preview_body)
		self.assertNotIn(".submit()", preview_body)
		self.assertNotIn("frappe.db.commit", preview_body)

	def test_submit_locks_checks_freshness_and_uses_erpnext_document_lifecycle(self):
		backend = (APP_ROOT / "professional_purchase_returns.py").read_text(encoding="utf-8")

		self.assertIn("FOR UPDATE", backend)
		self.assertIn("expected_source_modified", backend)
		self.assertIn("expected_modified != current_modified", backend)
		self.assertIn('_permission(source.doctype, "submit")', backend)
		self.assertIn("target.insert()", backend)
		self.assertIn("target.submit()", backend)
		self.assertIn('"posting_status": "Submitted"', backend)
		self.assertNotIn("ignore_permissions=True", backend)
		self.assertNotIn("frappe.db.commit", backend)
		self.assertNotIn('frappe.new_doc("GL Entry")', backend)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', backend)
		self.assertNotIn('frappe.new_doc("Payment Entry")', backend)
		self.assertNotIn('frappe.new_doc("Journal Entry")', backend)

	def test_standard_path_blocks_unhandled_serial_and_batch_stock_returns(self):
		backend = (APP_ROOT / "professional_purchase_returns.py").read_text(encoding="utf-8")
		overlay = (APP_ROOT / "public/js/professional_purchasing/ProfessionalPurchaseReturnReviewOverlay.vue").read_text(encoding="utf-8")

		self.assertIn('"has_serial_no"', backend)
		self.assertIn('"has_batch_no"', backend)
		self.assertIn("Serial Number handling requires Advanced ERPNext", backend)
		self.assertIn("Batch handling requires Advanced ERPNext", backend)
		self.assertIn("if review[\"blockers\"]", backend)
		self.assertIn("Advanced handling required", overlay)
		self.assertIn("standard_return_eligible", overlay)

	def test_slice_does_not_absorb_quality_inspection_or_landed_cost(self):
		backend = (APP_ROOT / "professional_purchase_returns.py").read_text(encoding="utf-8")
		overlay = (APP_ROOT / "public/js/professional_purchasing/ProfessionalPurchaseReturnReviewOverlay.vue").read_text(encoding="utf-8")
		combined = backend + overlay

		self.assertNotIn("Quality Inspection", combined)
		self.assertNotIn("Landed Cost", combined)


if __name__ == "__main__":
	unittest.main()
